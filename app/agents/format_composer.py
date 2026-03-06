from __future__ import annotations

from app.agents.base import BaseSwarmAgent
from app.models.schemas import AgentActionResult, AgentActionType, Idea, RunState
from app.services.llm import LLMService


class FormatComposerAgent(BaseSwarmAgent):
    def __init__(self, llm: LLMService | None = None) -> None:
        super().__init__("format_composer")
        self.llm = llm

    # ── Readiness ────────────────────────────────────────────────────────────

    def can_act(self, state: RunState) -> bool:
        # Act when there's a hook idea we haven't formatted yet this round
        formatted_parents = {
            pid
            for i in state.ideas
            if i.source_agent == self.name and i.round_created == state.round_number
            for pid in i.parent_idea_ids
        }
        hook_ideas = [
            i for i in state.ideas
            if "hook" in i.tags and i.idea_id not in formatted_parents
        ]
        return len(hook_ideas) > 0

    def priority(self, state: RunState) -> float:
        return 0.50

    # ── Core logic ───────────────────────────────────────────────────────────

    def act(self, state: RunState) -> AgentActionResult:
        if not state.ideas:
            return AgentActionResult(
                action_type=AgentActionType.critique,
                message="No ideas to compose into platform formats.",
            )

        # Pick the best unformatted hook idea
        formatted_parents = {
            pid
            for i in state.ideas
            if i.source_agent == self.name and i.round_created == state.round_number
            for pid in i.parent_idea_ids
        }
        hook_ideas = [
            i for i in state.ideas
            if "hook" in i.tags and i.idea_id not in formatted_parents
        ]
        parent = (
            max(hook_ideas, key=lambda i: state.scores.get(i.idea_id, 0.5) + state.confidence.get(i.idea_id, i.confidence))
            if hook_ideas
            else state.ideas[-1]
        )
        platform = state.campaign_input.platform.lower()
        recommended_format = (
            "talking-head + b-roll" if "reel" in platform or "tiktok" in platform else "demo-led short"
        )
        llm_message = "used deterministic fallback"

        title = f"{parent.title} - format package"
        description = f"{parent.description} Use format: {recommended_format}. End with clear CTA."
        hook = parent.hook
        confidence = 0.68

        if self.llm:
            prompt = (
                "You are a video format director for short-form social content.\n"
                "Package the parent idea into an executable video format with scene structure and CTA.\n"
                "Return exactly 4 lines in this format:\n"
                "TITLE: ...\nDESCRIPTION: ...\nHOOK: ...\nCONFIDENCE: [0.0-1.0]\n\n"
                f"PARENT IDEA: {parent.title} — {parent.description}\n"
                f"PLATFORM: {state.campaign_input.platform}\n"
                f"PRODUCT: {state.campaign_input.product_info}\n"
                f"CREATOR PROFILE: {state.campaign_input.creator_profile}\n"
                "The DESCRIPTION must include: video format type, scene-by-scene structure (3-4 scenes), and the CTA.\n"
                "Keep the HOOK as the literal opening line of the video.\n"
                "Set CONFIDENCE to how executable this format plan is (0.0-1.0).\n"
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

        formatted = Idea(
            title=title,
            description=description,
            hook=hook,
            source_agent=self.name,
            parent_idea_ids=[parent.idea_id],
            round_created=state.round_number,
            confidence=confidence,
            tags=["format", recommended_format],
            metadata={"recommended_format": recommended_format},
        )
        return AgentActionResult(
            action_type=AgentActionType.mutate,
            message=f"Wrapped idea {parent.idea_id} in executable {recommended_format} format ({llm_message}).",
            new_ideas=[formatted],
            updated_confidence={formatted.idea_id: confidence},
            lineage_updates={formatted.idea_id: [parent.idea_id]},
            payload={
                "thought": (
                    f"The hook concept needed a concrete, shootable structure for {state.campaign_input.platform}."
                ),
                "happened": (
                    f"Packaged {parent.idea_id} into {formatted.idea_id} using {recommended_format} format."
                ),
                "recommended_format": recommended_format,
                "model": llm_message,
            },
        )
