from __future__ import annotations

from app.agents.base import BaseSwarmAgent
from app.models.schemas import AgentActionResult, AgentActionType, Idea, RunState
from app.services.llm import LLMService


class TrendScoutAgent(BaseSwarmAgent):
    def __init__(self, llm: LLMService | None = None) -> None:
        super().__init__("trend_scout")
        self.llm = llm

    def act(self, state: RunState) -> AgentActionResult:
        trend_seed = ", ".join((state.campaign_input.global_trends + state.campaign_input.niche_trends)[:2])
        if not trend_seed:
            trend_seed = "rapid culture moments"

        llm_message = "used deterministic fallback"
        title = f"Trend-jacked {state.campaign_input.platform} challenge"
        description = (
            f"Position {state.campaign_input.product_info} inside {trend_seed} with native, "
            "repeatable challenge mechanics and remix prompts."
        )
        hook = f"This trend is everywhere, but nobody used it for {state.campaign_input.product_info} like this."

        if self.llm:
            prompt = (
                "You are a social content strategist. Generate one short-form concept.\n"
                "Return exactly 3 lines in this format:\n"
                "TITLE: ...\nDESCRIPTION: ...\nHOOK: ...\n\n"
                f"PRODUCT: {state.campaign_input.product_info}\n"
                f"AUDIENCE: {state.campaign_input.target_audience}\n"
                f"CREATOR: {state.campaign_input.creator_profile}\n"
                f"PLATFORM: {state.campaign_input.platform}\n"
                f"TRENDS: {trend_seed}\n"
            )
            try:
                llm_result = self.llm.complete(prompt)
                parsed = self._parse_lines(llm_result.text)
                title = parsed.get("title", title)
                description = parsed.get("description", description)
                hook = parsed.get("hook", hook)
                llm_message = f"used {llm_result.provider}:{llm_result.model}"
            except Exception as exc:
                llm_message = f"llm unavailable, fallback used ({exc})"

        idea = Idea(
            title=title,
            description=description,
            hook=hook,
            source_agent=self.name,
            round_created=state.round_number,
            tags=["trend", "velocity"],
            metadata={"platform": state.campaign_input.platform},
        )
        return AgentActionResult(
            action_type=AgentActionType.propose,
            message=f"Injected a trend-native concept into shared memory ({llm_message}).",
            new_ideas=[idea],
            updated_confidence={idea.idea_id: 0.62},
        )

    def _parse_lines(self, content: str) -> dict[str, str]:
        parsed: dict[str, str] = {}
        for line in content.splitlines():
            cleaned = line.strip()
            if cleaned.upper().startswith("TITLE:"):
                parsed["title"] = cleaned.split(":", 1)[1].strip()
            elif cleaned.upper().startswith("DESCRIPTION:"):
                parsed["description"] = cleaned.split(":", 1)[1].strip()
            elif cleaned.upper().startswith("HOOK:"):
                parsed["hook"] = cleaned.split(":", 1)[1].strip()
        return parsed
