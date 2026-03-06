from __future__ import annotations

from app.agents.base import BaseSwarmAgent
from app.models.schemas import AgentActionResult, AgentActionType, Idea, RunState
from app.services.llm import LLMService


class AudiencePsychologistAgent(BaseSwarmAgent):
    def __init__(self, llm: LLMService | None = None) -> None:
        super().__init__("audience_psychologist")
        self.llm = llm

    # ── Readiness ────────────────────────────────────────────────────────────

    def can_act(self, state: RunState) -> bool:
        # Bootstrap mode: if trend_scout is dead and nothing exists, we can seed
        trend_scout_dead = (
            "trend_scout" in state.killed_agents
            or state.agent_fail_counts.get("trend_scout", 0) >= 2
        )
        if not state.ideas and trend_scout_dead:
            return True

        # Normal mode: act for each unprocessed trend/velocity idea this round
        trend_ideas = [i for i in state.ideas if "trend" in i.tags or "velocity" in i.tags]
        processed_parents = {
            pid
            for i in state.ideas
            if i.source_agent == self.name and i.round_created == state.round_number
            for pid in i.parent_idea_ids
        }
        unprocessed = [i for i in trend_ideas if i.idea_id not in processed_parents]
        return len(unprocessed) > 0

    def priority(self, state: RunState) -> float:
        # High priority right after TrendScout fires
        return 0.75

    # ── Core logic ───────────────────────────────────────────────────────────

    def act(self, state: RunState) -> AgentActionResult:
        is_bootstrap = not state.ideas
        audience = state.campaign_input.target_audience

        if is_bootstrap:
            parent = None
            parent_ids: list[str] = []
        else:
            # Pick the most recent unprocessed trend idea
            processed_parents = {
                pid
                for i in state.ideas
                if i.source_agent == self.name and i.round_created == state.round_number
                for pid in i.parent_idea_ids
            }
            trend_ideas = [i for i in state.ideas if "trend" in i.tags or "velocity" in i.tags]
            unprocessed = [i for i in trend_ideas if i.idea_id not in processed_parents]
            parent = unprocessed[-1] if unprocessed else state.ideas[-1]
            parent_ids = [parent.idea_id]

        llm_message = "used deterministic fallback"
        parent_context = parent.title if parent else state.campaign_input.product_info

        title = f"{parent_context} - audience tension reframed"
        description = (
            f"Reframe for {audience}: start with a high-friction daily pain, then show "
            f"how {state.campaign_input.product_info} removes emotional resistance in under 10 seconds."
        )
        hook = f"If you are {audience}, this tiny shift changes your day instantly."
        confidence = 0.66

        if self.llm:
            parent_line = (
                f"PARENT IDEA: {parent.title} — {parent.description}\n"
                if parent else
                f"No parent idea yet. Generate a fresh concept for: {state.campaign_input.product_info}\n"
            )
            prompt = (
                "You are an audience psychology expert for social media content.\n"
                "Generate one content concept that reframes the parent idea through the lens of audience emotion and pain.\n"
                "Return exactly 4 lines in this format:\n"
                "TITLE: ...\nDESCRIPTION: ...\nHOOK: ...\nCONFIDENCE: [0.0-1.0]\n\n"
                f"{parent_line}"
                f"TARGET AUDIENCE: {audience}\n"
                f"PRODUCT: {state.campaign_input.product_info}\n"
                f"PLATFORM: {state.campaign_input.platform}\n"
                "Focus on emotional tension, identity, and the moment the audience recognises themselves.\n"
                "Set CONFIDENCE to how strongly you believe this concept will resonate (0.0-1.0).\n"
            )
            try:
                result = self.llm.complete(prompt)
                parsed = self._parse_lines(result.text)
                title = parsed.get("title", title)
                description = parsed.get("description", description)
                hook = parsed.get("hook", hook)
                confidence = float(parsed.get("confidence", str(confidence)))
                llm_message = f"used {result.provider}:{result.model}"
            except Exception as exc:
                llm_message = f"llm unavailable, fallback used ({exc})"

        mutation = Idea(
            title=title,
            description=description,
            hook=hook,
            source_agent=self.name,
            parent_idea_ids=parent_ids,
            round_created=state.round_number,
            confidence=confidence,
            tags=["audience", "emotion"],
        )
        updated_scores = {}
        if parent:
            updated_scores[parent.idea_id] = state.scores.get(parent.idea_id, 0.5) + 0.08

        return AgentActionResult(
            action_type=AgentActionType.mutate,
            message=(
                f"Mutated idea {parent_ids[0] if parent_ids else 'bootstrap'} "
                f"with audience psychology framing ({llm_message})."
            ),
            new_ideas=[mutation],
            updated_scores=updated_scores,
            updated_confidence={mutation.idea_id: confidence},
            lineage_updates={mutation.idea_id: parent_ids} if parent_ids else {},
            payload={
                "thought": (
                    f"{'Bootstrap seed' if is_bootstrap else 'Parent idea'} needed stronger emotional tension "
                    f"for {audience} to improve relatability."
                ),
                "happened": (
                    f"Created {mutation.idea_id} by reframing "
                    f"{'from scratch' if is_bootstrap else f'parent {parent_ids[0]}'} with audience psychology."
                ),
                "model": llm_message,
            },
        )
