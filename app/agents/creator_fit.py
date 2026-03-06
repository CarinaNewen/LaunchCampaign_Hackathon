from __future__ import annotations

from app.agents.base import BaseSwarmAgent
from app.models.schemas import AgentActionResult, AgentActionType, Idea, RunState
from app.services.llm import LLMService


class CreatorFitAgent(BaseSwarmAgent):
    def __init__(self, llm: LLMService | None = None) -> None:
        super().__init__("creator_fit")
        self.llm = llm

    # ── Readiness ────────────────────────────────────────────────────────────

    def can_act(self, state: RunState) -> bool:
        # Act when there's an audience/emotion idea we haven't yet built on this round
        audience_ideas = [
            i for i in state.ideas
            if "audience" in i.tags or "emotion" in i.tags
        ]
        processed_parents = {
            pid
            for i in state.ideas
            if i.source_agent == self.name and i.round_created == state.round_number
            for pid in i.parent_idea_ids
        }
        unprocessed = [i for i in audience_ideas if i.idea_id not in processed_parents]
        return len(unprocessed) > 0

    def priority(self, state: RunState) -> float:
        return 0.65

    # ── Core logic ───────────────────────────────────────────────────────────

    def act(self, state: RunState) -> AgentActionResult:
        if not state.ideas:
            return AgentActionResult(
                action_type=AgentActionType.critique,
                message="No ideas available to align with creator profile.",
            )

        # Prefer the highest-confidence unprocessed audience idea
        processed_parents = {
            pid
            for i in state.ideas
            if i.source_agent == self.name and i.round_created == state.round_number
            for pid in i.parent_idea_ids
        }
        audience_ideas = [
            i for i in state.ideas
            if ("audience" in i.tags or "emotion" in i.tags) and i.idea_id not in processed_parents
        ]
        parent = (
            max(audience_ideas, key=lambda i: state.confidence.get(i.idea_id, i.confidence))
            if audience_ideas
            else max(state.ideas, key=lambda i: state.confidence.get(i.idea_id, i.confidence))
        )
        creator = state.campaign_input.creator_profile
        llm_message = "used deterministic fallback"

        title = f"{parent.title} - creator-native spin"
        description = (
            f"Adapt concept to creator strengths ({creator}) with a natural POV sequence: "
            "cold open -> candid reaction -> practical payoff."
        )
        hook = "I tested this in my own creator workflow and the result surprised me."
        confidence = 0.64

        if self.llm:
            prompt = (
                "You are a creator strategy consultant who specialises in authentic sponsored content.\n"
                "Adapt the parent idea to fit the creator's style so it feels native, not like an ad.\n"
                "Return exactly 4 lines in this format:\n"
                "TITLE: ...\nDESCRIPTION: ...\nHOOK: ...\nCONFIDENCE: [0.0-1.0]\n\n"
                f"PARENT IDEA: {parent.title} — {parent.description}\n"
                f"CREATOR PROFILE: {creator}\n"
                f"PRODUCT: {state.campaign_input.product_info}\n"
                f"PLATFORM: {state.campaign_input.platform}\n"
                "The concept must feel like it comes from the creator's lived experience, not a brand brief.\n"
                "Set CONFIDENCE to how well this concept fits the creator's authentic voice (0.0-1.0).\n"
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

        idea = Idea(
            title=title,
            description=description,
            hook=hook,
            source_agent=self.name,
            parent_idea_ids=[parent.idea_id],
            round_created=state.round_number,
            confidence=confidence,
            tags=["creator-fit", "authenticity"],
        )
        return AgentActionResult(
            action_type=AgentActionType.mutate,
            message=f"Aligned idea {parent.idea_id} to creator style and delivery ({llm_message}).",
            new_ideas=[idea],
            updated_scores={parent.idea_id: state.scores.get(parent.idea_id, 0.5) + 0.06},
            updated_confidence={idea.idea_id: confidence},
            lineage_updates={idea.idea_id: [parent.idea_id]},
            payload={
                "thought": (
                    f"The highest-confidence audience concept should sound native to the creator profile: {creator}."
                ),
                "happened": f"Produced {idea.idea_id} as a creator-fit adaptation of {parent.idea_id}.",
                "model": llm_message,
            },
        )
