from __future__ import annotations

from app.agents.base import BaseSwarmAgent
from app.models.schemas import AgentActionResult, AgentActionType, Idea, RunState
from app.services.llm import LLMService


class HookSmithAgent(BaseSwarmAgent):
    def __init__(self, llm: LLMService | None = None) -> None:
        super().__init__("hook_smith")
        self.llm = llm

    # ── Readiness ────────────────────────────────────────────────────────────

    def can_act(self, state: RunState) -> bool:
        # Target creator-fit and audience ideas that haven't been given a hook yet.
        # Limiting to these high-value tags keeps activations focused and budget-efficient.
        hooked_parents = {
            pid
            for i in state.ideas
            if i.source_agent == self.name and i.round_created == state.round_number
            for pid in i.parent_idea_ids
        }
        target_tags = {"creator-fit", "authenticity", "audience", "emotion"}
        eligible = [
            i for i in state.ideas
            if i.idea_id not in hooked_parents
            and i.source_agent != self.name
            and target_tags.intersection(i.tags)
        ]
        return len(eligible) > 0

    def priority(self, state: RunState) -> float:
        return 0.55

    # ── Core logic ───────────────────────────────────────────────────────────

    def act(self, state: RunState) -> AgentActionResult:
        if not state.ideas:
            return AgentActionResult(
                action_type=AgentActionType.critique,
                message="No ideas available for hook refinement.",
            )

        # Pick the best unprocessed creator-fit or audience idea to hook
        hooked_parents = {
            pid
            for i in state.ideas
            if i.source_agent == self.name and i.round_created == state.round_number
            for pid in i.parent_idea_ids
        }
        target_tags = {"creator-fit", "authenticity", "audience", "emotion"}
        eligible = [
            i for i in state.ideas
            if i.idea_id not in hooked_parents
            and i.source_agent != self.name
            and target_tags.intersection(i.tags)
        ]
        if not eligible:
            eligible = [
                i for i in state.ideas
                if i.idea_id not in hooked_parents and i.source_agent != self.name
            ]
        # Prefer the highest-scoring eligible idea
        parent = max(
            eligible,
            key=lambda i: state.scores.get(i.idea_id, 0.5) + state.confidence.get(i.idea_id, i.confidence),
        )
        platform = state.campaign_input.platform
        llm_message = "used deterministic fallback"

        title = f"{parent.title} - hook-heavy variant"
        description = parent.description
        hook = f"Stop scrolling: {state.campaign_input.product_info} wins on {platform} in 15 seconds."
        confidence = 0.67

        if self.llm:
            prompt = (
                "You are a viral hook writer specialising in short-form video content.\n"
                "Generate a hook-first variant of the parent idea — the opening 3 seconds must stop the scroll.\n"
                "Return exactly 4 lines in this format:\n"
                "TITLE: ...\nDESCRIPTION: ...\nHOOK: ...\nCONFIDENCE: [0.0-1.0]\n\n"
                f"PARENT IDEA: {parent.title} — {parent.description}\n"
                f"PARENT HOOK: {parent.hook}\n"
                f"PRODUCT: {state.campaign_input.product_info}\n"
                f"PLATFORM: {platform}\n"
                f"TARGET AUDIENCE: {state.campaign_input.target_audience}\n"
                "The HOOK line must be the literal first words spoken or shown on screen. Make it punchy, specific, and curiosity-driven.\n"
                "Set CONFIDENCE to how likely this hook is to stop the scroll (0.0-1.0).\n"
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

        hook_variant = Idea(
            title=title,
            description=description,
            hook=hook,
            source_agent=self.name,
            parent_idea_ids=[parent.idea_id],
            round_created=state.round_number,
            confidence=confidence,
            tags=["hook", "retention"],
        )
        return AgentActionResult(
            action_type=AgentActionType.mutate,
            message=f"Generated a stronger hook variant from idea {parent.idea_id} ({llm_message}).",
            new_ideas=[hook_variant],
            updated_confidence={hook_variant.idea_id: confidence},
            lineage_updates={hook_variant.idea_id: [parent.idea_id]},
            payload={
                "thought": f"The best available idea needed a sharper first 3-second hook for {platform}.",
                "happened": (
                    f"Generated hook-forward variant {hook_variant.idea_id} from parent {parent.idea_id}."
                ),
                "model": llm_message,
            },
        )
