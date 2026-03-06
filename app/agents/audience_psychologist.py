from __future__ import annotations

from app.agents.base import BaseSwarmAgent
from app.models.schemas import AgentActionResult, AgentActionType, Idea, RunState


class AudiencePsychologistAgent(BaseSwarmAgent):
    def __init__(self) -> None:
        super().__init__("audience_psychologist")

    def act(self, state: RunState) -> AgentActionResult:
        if not state.ideas:
            return AgentActionResult(
                action_type=AgentActionType.critique,
                message="No ideas yet; waiting for swarm memory to populate.",
            )

        parent = state.ideas[-1]
        audience = state.campaign_input.target_audience
        mutation = Idea(
            title=f"{parent.title} - audience tension reframed",
            description=(
                f"Reframe for {audience}: start with a high-friction daily pain, then show "
                f"how {state.campaign_input.product_info} removes emotional resistance in under 10 seconds."
            ),
            hook=f"If you are {audience}, this tiny shift changes your day instantly.",
            source_agent=self.name,
            parent_idea_ids=[parent.idea_id],
            round_created=state.round_number,
            tags=["audience", "emotion"],
        )
        return AgentActionResult(
            action_type=AgentActionType.mutate,
            message=f"Mutated idea {parent.idea_id} with audience psychology framing.",
            new_ideas=[mutation],
            updated_scores={parent.idea_id: state.scores.get(parent.idea_id, 0.5) + 0.08},
            updated_confidence={mutation.idea_id: 0.66},
            lineage_updates={mutation.idea_id: [parent.idea_id]},
        )
