from __future__ import annotations

from app.agents.base import BaseSwarmAgent
from app.models.schemas import AgentActionResult, AgentActionType, Idea, RunState


class CriticMutatorAgent(BaseSwarmAgent):
    def __init__(self) -> None:
        super().__init__("critic_mutator")

    def act(self, state: RunState) -> AgentActionResult:
        if len(state.ideas) < 2:
            return AgentActionResult(
                action_type=AgentActionType.critique,
                message="Not enough ideas to run merge critique.",
            )

        scored = sorted(
            state.ideas,
            key=lambda idea: state.scores.get(idea.idea_id, 0.5) + state.confidence.get(idea.idea_id, idea.confidence),
            reverse=True,
        )
        first, second = scored[0], scored[1]

        merged = Idea(
            title=f"Converged: {first.title} + {second.title}",
            description=(
                f"Merge strongest elements: ({first.description}) + ({second.description}). "
                "Deliver as one tightly scoped experiment with two hook variants."
            ),
            hook=f"{first.hook} / ALT: {second.hook}",
            source_agent=self.name,
            parent_idea_ids=[first.idea_id, second.idea_id],
            round_created=state.round_number,
            tags=["merge", "convergence"],
        )
        return AgentActionResult(
            action_type=AgentActionType.merge,
            message=f"Critiqued swarm set and converged top ideas {first.idea_id}, {second.idea_id}.",
            new_ideas=[merged],
            updated_scores={
                first.idea_id: state.scores.get(first.idea_id, 0.5) + 0.1,
                second.idea_id: state.scores.get(second.idea_id, 0.5) + 0.08,
                merged.idea_id: 0.75,
            },
            updated_confidence={merged.idea_id: 0.74},
            lineage_updates={merged.idea_id: [first.idea_id, second.idea_id]},
        )
