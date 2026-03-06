from __future__ import annotations

from app.agents.base import BaseSwarmAgent
from app.models.schemas import AgentActionResult, AgentActionType, Idea, RunState
from app.services.llm import LLMService


class TrendScoutAgent(BaseSwarmAgent):
    def __init__(self, llm: LLMService | None = None) -> None:
        super().__init__("trend_scout")
        self.llm = llm

    # ── Readiness ────────────────────────────────────────────────────────────

    def can_act(self, state: RunState) -> bool:
        """Fire once per round to seed the first idea for that round."""
        our_seeds_this_round = [
            i for i in state.ideas
            if i.source_agent == self.name and i.round_created == state.round_number
        ]
        return len(our_seeds_this_round) == 0

    def priority(self, state: RunState) -> float:
        # Maximum urgency when the pool is empty — nothing else can act without a seed
        return 1.0 if not state.ideas else 0.6

    # ── Core logic ───────────────────────────────────────────────────────────

    def act(self, state: RunState) -> AgentActionResult:
        trend_seed = ", ".join((state.campaign_input.global_trends + state.campaign_input.niche_trends)[:2])
        if not trend_seed:
            trend_seed = "rapid culture moments"

        prev_best = None
        parent_ids: list[str] = []
        if state.round_number > 1 and state.ideas:
            prev_best = max(
                state.ideas,
                key=lambda i: state.scores.get(i.idea_id, 0.5) + state.confidence.get(i.idea_id, i.confidence),
            )
            parent_ids = [prev_best.idea_id]

        llm_message = "used deterministic fallback"
        title = f"Trend-jacked {state.campaign_input.platform} challenge"
        description = (
            f"Position {state.campaign_input.product_info} inside {trend_seed} with native, "
            "repeatable challenge mechanics and remix prompts."
        )
        hook = f"This trend is everywhere, but nobody used it for {state.campaign_input.product_info} like this."
        confidence = 0.62

        if self.llm:
            prev_context = (
                f"PREVIOUS BEST IDEA: {prev_best.title} — {prev_best.description}\n"
                if prev_best else ""
            )
            prompt = (
                "You are a social content strategist. Generate one fresh short-form concept.\n"
                "Return exactly 4 lines in this format:\n"
                "TITLE: ...\nDESCRIPTION: ...\nHOOK: ...\nCONFIDENCE: [0.0-1.0]\n\n"
                f"PRODUCT: {state.campaign_input.product_info}\n"
                f"AUDIENCE: {state.campaign_input.target_audience}\n"
                f"CREATOR: {state.campaign_input.creator_profile}\n"
                f"PLATFORM: {state.campaign_input.platform}\n"
                f"TRENDS: {trend_seed}\n"
                f"ROUND: {state.round_number}\n"
                f"{prev_context}"
                "Generate a DIFFERENT angle from the previous idea if one is provided.\n"
                "Set CONFIDENCE to how strongly you believe this concept will perform (0.0-1.0).\n"
            )
            try:
                llm_result = self.llm.complete(prompt)
                parsed = self._parse_lines(llm_result.text)
                title = parsed.get("title", title)
                description = parsed.get("description", description)
                hook = parsed.get("hook", hook)
                confidence = float(parsed.get("confidence", str(confidence)))
                llm_message = f"used {llm_result.provider}:{llm_result.model}"
            except Exception as exc:
                llm_message = f"llm unavailable, fallback used ({exc})"

        idea = Idea(
            title=title,
            description=description,
            hook=hook,
            source_agent=self.name,
            parent_idea_ids=parent_ids,
            round_created=state.round_number,
            confidence=confidence,
            tags=["trend", "velocity"],
            metadata={"platform": state.campaign_input.platform},
        )
        lineage_updates = {idea.idea_id: parent_ids} if parent_ids else {}
        return AgentActionResult(
            action_type=AgentActionType.propose,
            message=f"Injected a trend-native concept into shared memory ({llm_message}).",
            new_ideas=[idea],
            updated_confidence={idea.idea_id: confidence},
            lineage_updates=lineage_updates,
            payload={
                "thought": (
                    f"Lead with trend momentum ({trend_seed}) to seed a high-velocity concept for round {state.round_number}."
                ),
                "happened": f"Proposed new root concept {idea.idea_id} from trend signals.",
                "model": llm_message,
            },
        )
