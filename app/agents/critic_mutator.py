from __future__ import annotations

from app.agents.base import BaseSwarmAgent
from app.models.schemas import AgentActionResult, AgentActionType, Idea, RunState
from app.services.llm import LLMService


class CriticMutatorAgent(BaseSwarmAgent):
    def __init__(self, llm: LLMService | None = None) -> None:
        super().__init__("critic_mutator")
        self.llm = llm

    # ── Readiness ────────────────────────────────────────────────────────────

    def can_act(self, state: RunState) -> bool:
        # Two-step behaviour per round:
        # 1) Critique existing pool (no new idea)
        # 2) Merge top candidates into a converged idea
        if len(state.ideas) < 2:
            return False
        events_this_round = [
            e for e in state.event_history
            if e.agent_name == self.name and e.round_number == state.round_number
        ]
        critiqued = any(e.action_type == AgentActionType.critique for e in events_this_round)
        merged = any(e.action_type == AgentActionType.merge for e in events_this_round)
        return not (critiqued and merged)

    def priority(self, state: RunState) -> float:
        events_this_round = [
            e for e in state.event_history
            if e.agent_name == self.name and e.round_number == state.round_number
        ]
        critiqued = any(e.action_type == AgentActionType.critique for e in events_this_round)
        # Critique should happen before merge in each round.
        if not critiqued:
            return 0.72
        # Merge stays lower-priority than direct ideation agents, but rises as pool grows.
        return 0.3 + min(len(state.ideas) * 0.02, 0.4)

    # ── Core logic ───────────────────────────────────────────────────────────

    def act(self, state: RunState) -> AgentActionResult:
        if len(state.ideas) < 2:
            return AgentActionResult(
                action_type=AgentActionType.critique,
                message="Not enough ideas to run merge critique.",
            )

        events_this_round = [
            e for e in state.event_history
            if e.agent_name == self.name and e.round_number == state.round_number
        ]
        critiqued_this_round = any(e.action_type == AgentActionType.critique for e in events_this_round)

        scored = sorted(
            state.ideas,
            key=lambda idea: state.scores.get(idea.idea_id, 0.5) + state.confidence.get(idea.idea_id, idea.confidence),
            reverse=True,
        )
        first, second = scored[0], scored[1]

        # Step 1: critique pass (normal path). This feeds disagreement/consensus metrics.
        if not critiqued_this_round:
            top_score = state.scores.get(first.idea_id, 0.5) + state.confidence.get(first.idea_id, first.confidence)
            second_score = state.scores.get(second.idea_id, 0.5) + state.confidence.get(second.idea_id, second.confidence)
            score_gap = abs(top_score - second_score)
            needs_merge = score_gap < 0.22
            concern = (
                "two leaders are still too close to declare a winner"
                if needs_merge else
                "winner exists, but execution details are still fragmented across candidates"
            )
            return AgentActionResult(
                action_type=AgentActionType.critique,
                message=(
                    f"Critiqued top ideas {first.idea_id} vs {second.idea_id}; "
                    f"{'convergence required' if needs_merge else 'merge still recommended'}."
                ),
                payload={
                    "thought": (
                        f"Top candidates are {first.idea_id} and {second.idea_id}; "
                        f"score gap={score_gap:.2f} indicates unresolved trade-offs."
                    ),
                    "happened": (
                        f"Logged critique for round {state.round_number}: {concern}. "
                        "Next pass will synthesise into one converged concept."
                    ),
                    "score_gap": round(score_gap, 4),
                    "top_candidates": [first.idea_id, second.idea_id],
                    "needs_merge": needs_merge,
                },
            )

        llm_message = "used deterministic fallback"

        title = f"Converged: {first.title} + {second.title}"
        description = (
            f"Merge strongest elements: ({first.description}) + ({second.description}). "
            "Deliver as one tightly scoped experiment with two hook variants."
        )
        hook = f"{first.hook} / ALT: {second.hook}"
        confidence = 0.74

        # Default peer scores: small upvote for all ideas visible to this agent
        peer_score_updates: dict[str, float] = {
            idea.idea_id: state.scores.get(idea.idea_id, 0.5) + 0.03
            for idea in state.ideas
        }
        # Stronger boosts for the top two
        peer_score_updates[first.idea_id] = state.scores.get(first.idea_id, 0.5) + 0.10
        peer_score_updates[second.idea_id] = state.scores.get(second.idea_id, 0.5) + 0.08

        if self.llm:
            # Summarise the idea pool for the LLM (cap at last 8 to keep prompt short)
            pool = state.ideas[-8:]
            ideas_summary = "\n".join(
                f"  {i.idea_id}: {i.title} (score={state.scores.get(i.idea_id, 0.5):.2f}, "
                f"conf={state.confidence.get(i.idea_id, i.confidence):.2f})"
                for i in pool
            )
            prompt = (
                "You are a creative director who synthesises competing ideas into a single, stronger concept.\n"
                "Also score EVERY idea in the pool on quality (0.0-1.0).\n"
                "Return in this exact format:\n"
                "TITLE: ...\nDESCRIPTION: ...\nHOOK: ...\nCONFIDENCE: [0.0-1.0]\n"
                "SCORES: idea_id=score, idea_id=score, ...\n\n"
                f"IDEA POOL:\n{ideas_summary}\n\n"
                f"TOP IDEA A: {first.title} — {first.description}\nHOOK A: {first.hook}\n\n"
                f"TOP IDEA B: {second.title} — {second.description}\nHOOK B: {second.hook}\n\n"
                f"PRODUCT: {state.campaign_input.product_info}\n"
                f"PLATFORM: {state.campaign_input.platform}\n"
                f"TARGET AUDIENCE: {state.campaign_input.target_audience}\n"
                "The merged concept must have a clear unique angle, not just list both ideas. Be bold and decisive.\n"
                "In SCORES list every idea_id from the pool with your quality score.\n"
            )
            try:
                result = self.llm.complete(prompt)
                parsed = self._parse_lines(result.text)
                title = parsed.get("title", title)
                description = parsed.get("description", description)
                hook = parsed.get("hook", hook)
                confidence = float(parsed.get("confidence", str(confidence)))
                llm_message = f"used {result.provider}:{result.model}"

                # Parse peer scores from LLM: "idea_abc=0.82, idea_def=0.61, ..."
                if "scores" in parsed:
                    for token in parsed["scores"].split(","):
                        token = token.strip()
                        if "=" in token:
                            parts = token.split("=", 1)
                            idea_id = parts[0].strip()
                            try:
                                vote = max(0.0, min(1.0, float(parts[1].strip())))
                                peer_score_updates[idea_id] = vote
                            except ValueError:
                                pass
            except Exception as exc:
                llm_message = f"llm unavailable, fallback used ({exc})"

        merged = Idea(
            title=title,
            description=description,
            hook=hook,
            source_agent=self.name,
            parent_idea_ids=[first.idea_id, second.idea_id],
            round_created=state.round_number,
            confidence=confidence,
            tags=["merge", "convergence"],
        )
        peer_score_updates[merged.idea_id] = 0.75

        return AgentActionResult(
            action_type=AgentActionType.merge,
            message=f"Critiqued swarm set, scored all ideas, converged top {first.idea_id} + {second.idea_id} ({llm_message}).",
            new_ideas=[merged],
            updated_scores=peer_score_updates,
            updated_confidence={merged.idea_id: confidence},
            lineage_updates={merged.idea_id: [first.idea_id, second.idea_id]},
            payload={
                "thought": (
                    f"Top candidates {first.idea_id} and {second.idea_id} had complementary strengths. "
                    f"Scored all {len(state.ideas)} ideas in pool."
                ),
                "happened": f"Merged both into converged idea {merged.idea_id} and peer-scored the full pool.",
                "model": llm_message,
                "peer_scores_cast": len(peer_score_updates),
            },
        )
