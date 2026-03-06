from __future__ import annotations

from app.agents.base import BaseSwarmAgent
from app.models.schemas import AgentActionResult, AgentActionType, Idea, RunState


class FormatComposerAgent(BaseSwarmAgent):
    def __init__(self) -> None:
        super().__init__("format_composer")

    def act(self, state: RunState) -> AgentActionResult:
        if not state.ideas:
            return AgentActionResult(
                action_type=AgentActionType.critique,
                message="No ideas to compose into platform formats.",
            )

        parent = state.ideas[-1]
        platform = state.campaign_input.platform.lower()
        recommended_format = "talking-head + b-roll" if "reel" in platform or "tiktok" in platform else "demo-led short"
        formatted = Idea(
            title=f"{parent.title} - format package",
            description=f"{parent.description} Use format: {recommended_format}. End with clear CTA.",
            hook=parent.hook,
            source_agent=self.name,
            parent_idea_ids=[parent.idea_id],
            round_created=state.round_number,
            tags=["format", recommended_format],
            metadata={"recommended_format": recommended_format},
        )
        return AgentActionResult(
            action_type=AgentActionType.mutate,
            message=f"Wrapped idea {parent.idea_id} in executable {recommended_format} format.",
            new_ideas=[formatted],
            updated_confidence={formatted.idea_id: 0.68},
            lineage_updates={formatted.idea_id: [parent.idea_id]},
            payload={"recommended_format": recommended_format},
        )
