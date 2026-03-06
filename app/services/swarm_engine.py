from __future__ import annotations

from dataclasses import dataclass

from app.agents.audience_psychologist import AudiencePsychologistAgent
from app.agents.base import BaseSwarmAgent
from app.agents.creator_fit import CreatorFitAgent
from app.agents.critic_mutator import CriticMutatorAgent
from app.agents.format_composer import FormatComposerAgent
from app.agents.hook_smith import HookSmithAgent
from app.agents.trend_scout import TrendScoutAgent
from app.models.schemas import (
    AgentActionType,
    AgentStatus,
    CampaignInput,
    FinalOutput,
    RunState,
    SwarmEvent,
)
from app.services.llm import LLMService
from app.services.state_store import StateStore


@dataclass
class SharedStateManager:
    store: StateStore

    def load(self, run_id: str) -> RunState:
        run = self.store.get_run(run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found.")
        return run

    def save(self, run: RunState) -> RunState:
        return self.store.save_run(run.run_id, run)

    def add_event(self, run_id: str, event: SwarmEvent) -> None:
        self.store.append_event(run_id, event)

    def set_agent_status(self, run_id: str, agent_name: str, status: AgentStatus) -> None:
        self.store.update_agent_status(run_id, agent_name, status)


class SwarmEngine:
    def __init__(self, store: StateStore, llm: LLMService | None = None) -> None:
        self.store = store
        self.state = SharedStateManager(store=store)
        self.llm = llm or LLMService()
        self.agents: list[BaseSwarmAgent] = [
            TrendScoutAgent(llm=self.llm),
            AudiencePsychologistAgent(),
            CreatorFitAgent(),
            HookSmithAgent(),
            FormatComposerAgent(),
            CriticMutatorAgent(),
        ]

    def start_run(self, campaign_input: CampaignInput) -> RunState:
        run = RunState(
            campaign_input=campaign_input,
            agent_statuses={agent.name: AgentStatus.idle for agent in self.agents},
        )
        return self.store.create_run(run)

    def run_rounds(self, run_id: str, max_rounds: int) -> RunState:
        for round_index in range(1, max_rounds + 1):
            run = self.state.load(run_id)
            run.round_number = round_index
            self.state.save(run)

            for agent in self.agents:
                try:
                    self.state.set_agent_status(run_id, agent.name, AgentStatus.running)
                    run = self.state.load(run_id)
                    result = agent.act(run)

                    run = self.state.load(run_id)
                    for idea in result.new_ideas:
                        run.ideas.append(idea)
                    run.scores.update(result.updated_scores)
                    run.confidence.update(result.updated_confidence)
                    for child, parents in result.lineage_updates.items():
                        existing = run.lineage.get(child, [])
                        run.lineage[child] = list(dict.fromkeys(existing + parents))

                    self.state.save(run)
                    self.state.add_event(
                        run_id,
                        SwarmEvent(
                            run_id=run_id,
                            agent_name=agent.name,
                            round_number=round_index,
                            action_type=result.action_type,
                            message=result.message,
                            idea_ids=[idea.idea_id for idea in result.new_ideas],
                            payload=result.payload,
                        ),
                    )
                    self.state.set_agent_status(run_id, agent.name, AgentStatus.done)
                except Exception as exc:  # pragma: no cover - defensive for demo resilience
                    self.state.add_event(
                        run_id,
                        SwarmEvent(
                            run_id=run_id,
                            agent_name=agent.name,
                            round_number=round_index,
                            action_type=AgentActionType.critique,
                            message=f"Agent failed but swarm continued: {exc}",
                            payload={"error": str(exc)},
                        ),
                    )
                    self.state.set_agent_status(run_id, agent.name, AgentStatus.failed)

        final = self._build_final_output(self.state.load(run_id))
        final_run = self.state.load(run_id)
        final_run.final_output = final
        self.state.save(final_run)
        return self.state.load(run_id)

    def _build_final_output(self, run: RunState) -> FinalOutput:
        ranked = sorted(
            run.ideas,
            key=lambda idea: run.scores.get(idea.idea_id, 0.5) + run.confidence.get(idea.idea_id, idea.confidence),
            reverse=True,
        )
        top_ideas = ranked[:4]
        hooks = list(dict.fromkeys([idea.hook for idea in top_ideas]))
        formats: list[str] = []
        for idea in top_ideas:
            value = idea.metadata.get("recommended_format")
            if isinstance(value, str):
                formats.append(value)
        formats = list(dict.fromkeys(formats))

        strategy_summary = (
            f"Swarm converged after {run.round_number} rounds on {len(top_ideas)} high-potential concepts "
            f"for {run.campaign_input.platform}, combining trend velocity, audience tension, creator fit, "
            "and hook-first delivery."
        )
        lineage_summary = [
            f"{idea.idea_id} <- {', '.join(run.lineage.get(idea.idea_id, [])) or 'root'}" for idea in top_ideas
        ]
        posting_plan = [
            "Week 1: Ship top concept with 2 hook variants.",
            "Week 1: Post runner-up concept in alternate format.",
            "Week 2: Scale winner and remix with UGC stitching.",
        ]
        return FinalOutput(
            strategy_summary=strategy_summary,
            content_concepts=top_ideas,
            hook_library=hooks,
            recommended_formats=formats,
            posting_experiment_plan=posting_plan,
            lineage_summary=lineage_summary,
        )
