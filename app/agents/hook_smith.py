from __future__ import annotations

from app.agents.base import BaseSwarmAgent
from app.models.schemas import AgentActionResult, AgentActionType, Idea, RunState


class HookSmithAgent(BaseSwarmAgent):
    def __init__(self) -> None:
        super().__init__("hook_smith")

    def act(self, state: RunState) -> AgentActionResult:
        if not state.ideas:
            return AgentActionResult(
                action_type=AgentActionType.critique,
                message="No ideas available for hook refinement.",
            )

        parent = state.ideas[-1]
        platform = state.campaign_input.platform
        hook_variant = Idea(
            title=f"{parent.title} - hook-heavy variant",
            description=parent.description,
            hook=f"Stop scrolling: {state.campaign_input.product_info} wins on {platform} in 15 seconds.",
            source_agent=self.name,
            parent_idea_ids=[parent.idea_id],
            round_created=state.round_number,
            tags=["hook", "retention"],
        )
        return AgentActionResult(
            action_type=AgentActionType.mutate,
            message=f"Generated a stronger hook variant from idea {parent.idea_id}.",
            new_ideas=[hook_variant],
            updated_confidence={hook_variant.idea_id: 0.67},
            lineage_updates={hook_variant.idea_id: [parent.idea_id]},
        )
