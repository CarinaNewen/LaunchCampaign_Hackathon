from __future__ import annotations

from app.agents.base import BaseSwarmAgent
from app.models.schemas import AgentActionResult, AgentActionType, Idea, RunState


class CreatorFitAgent(BaseSwarmAgent):
    def __init__(self) -> None:
        super().__init__("creator_fit")

    def act(self, state: RunState) -> AgentActionResult:
        if not state.ideas:
            return AgentActionResult(
                action_type=AgentActionType.critique,
                message="No ideas available to align with creator profile.",
            )

        parent = max(state.ideas, key=lambda i: state.confidence.get(i.idea_id, i.confidence))
        creator = state.campaign_input.creator_profile
        idea = Idea(
            title=f"{parent.title} - creator-native spin",
            description=(
                f"Adapt concept to creator strengths ({creator}) with a natural POV sequence: "
                "cold open -> candid reaction -> practical payoff."
            ),
            hook=f"I tested this in my own creator workflow and the result surprised me.",
            source_agent=self.name,
            parent_idea_ids=[parent.idea_id],
            round_created=state.round_number,
            tags=["creator-fit", "authenticity"],
        )
        return AgentActionResult(
            action_type=AgentActionType.mutate,
            message=f"Aligned idea {parent.idea_id} to creator style and delivery.",
            new_ideas=[idea],
            updated_scores={parent.idea_id: state.scores.get(parent.idea_id, 0.5) + 0.06},
            updated_confidence={idea.idea_id: 0.64},
            lineage_updates={idea.idea_id: [parent.idea_id]},
        )
