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
            AudiencePsychologistAgent(llm=self.llm),
            CreatorFitAgent(llm=self.llm),
            HookSmithAgent(llm=self.llm),
            FormatComposerAgent(llm=self.llm),
            CriticMutatorAgent(llm=self.llm),
        ]

    def start_run(self, campaign_input: CampaignInput) -> RunState:
        run = RunState(
            campaign_input=campaign_input,
            agent_statuses={agent.name: AgentStatus.idle for agent in self.agents},
        )
        return self.store.create_run(run)

    def run_rounds(self, run_id: str, max_rounds: int) -> RunState:
        # Budget: each agent can fire up to 2× per round (state changes can re-qualify agents)
        budget_per_round = len(self.agents) * 2

        for round_index in range(1, max_rounds + 1):
            run = self.state.load(run_id)
            run.round_number = round_index
            self.state.save(run)

            activations_this_round = 0

            while activations_this_round < budget_per_round:
                run = self.state.load(run_id)

                # Build the eligible set: ready AND not killed
                eligible = [
                    a for a in self.agents
                    if a.name not in run.killed_agents and a.can_act(run)
                ]

                if not eligible:
                    # Quiescence: no agent has work to do — round is complete
                    break

                # Pick the highest-priority ready agent (list position breaks ties)
                agent = max(eligible, key=lambda a: a.priority(run))
                self._run_agent(run_id, agent, round_index)
                activations_this_round += 1

        final = self._build_final_output(self.state.load(run_id))
        final_run = self.state.load(run_id)
        final_run.final_output = final
        self.state.save(final_run)
        return self.state.load(run_id)

    def _run_agent(self, run_id: str, agent: BaseSwarmAgent, round_index: int) -> None:
        """Run one agent activation. Isolated so the outer loop stays clean."""
        try:
            self.state.set_agent_status(run_id, agent.name, AgentStatus.running)
            run = self.state.load(run_id)
            result = agent.act(run)

            run = self.state.load(run_id)
            for idea in result.new_ideas:
                run.ideas.append(idea)

            # Peer-vote score merging: final score = mean of all votes cast
            for idea_id, new_score in result.updated_scores.items():
                run.peer_votes.setdefault(idea_id, []).append(new_score)
                run.scores[idea_id] = sum(run.peer_votes[idea_id]) / len(run.peer_votes[idea_id])

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
            run = self.state.load(run_id)
            run.agent_fail_counts[agent.name] = run.agent_fail_counts.get(agent.name, 0) + 1

            # Auto-kill after 2 consecutive failures so the swarm stops wasting budget
            if run.agent_fail_counts[agent.name] >= 2 and agent.name not in run.killed_agents:
                run.killed_agents.append(agent.name)
                run.agent_statuses[agent.name] = AgentStatus.failed
                self.state.save(run)
                self.state.add_event(
                    run_id,
                    SwarmEvent(
                        run_id=run_id,
                        agent_name=agent.name,
                        round_number=round_index,
                        action_type=AgentActionType.critique,
                        message=f"{agent.name} auto-killed after 2 consecutive failures.",
                        payload={"auto_killed": True, "error": str(exc)},
                    ),
                )
            else:
                self.state.save(run)
                self.state.add_event(
                    run_id,
                    SwarmEvent(
                        run_id=run_id,
                        agent_name=agent.name,
                        round_number=round_index,
                        action_type=AgentActionType.critique,
                        message=f"Agent failed but swarm continued: {exc}",
                        payload={"error": str(exc), "fail_count": run.agent_fail_counts[agent.name]},
                    ),
                )
            self.state.set_agent_status(run_id, agent.name, AgentStatus.failed)

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

        lineage_summary = [
            f"{idea.idea_id} <- {', '.join(run.lineage.get(idea.idea_id, [])) or 'root'}" for idea in top_ideas
        ]

        # LLM-synthesized strategy summary
        strategy_summary = (
            f"Swarm converged after {run.round_number} rounds on "
            f"{len(top_ideas)} high-potential concepts for {run.campaign_input.platform}."
        )
        posting_plan = [
            "Week 1: Ship top concept with 2 hook variants.",
            "Week 1: Post runner-up concept in alternate format.",
            "Week 2: Scale winner and remix with UGC stitching.",
        ]

        if self.llm:
            concepts_text = "\n".join(
                f"- {i.title}: {i.description[:120]}" for i in top_ideas
            )
            summary_prompt = (
                f"Write a sharp 2-sentence content strategy summary for a {run.campaign_input.platform} campaign.\n"
                f"Product: {run.campaign_input.product_info}\n"
                f"Audience: {run.campaign_input.target_audience}\n"
                f"Top concepts from a multi-agent swarm ({run.round_number} rounds):\n"
                f"{concepts_text}\n"
                "Be specific and actionable. No generic phrases.\n"
                "Return ONLY the 2-sentence summary, nothing else.\n"
            )
            plan_prompt = (
                f"Write a 3-item weekly posting experiment plan for this {run.campaign_input.platform} campaign.\n"
                f"Product: {run.campaign_input.product_info}\n"
                f"Top concept: {top_ideas[0].title if top_ideas else 'N/A'}\n"
                "Format: return exactly 3 lines, each starting with 'Week N:'.\n"
            )
            try:
                summary_result = self.llm.complete(summary_prompt)
                strategy_summary = summary_result.text.strip() or strategy_summary
            except Exception:
                pass

            try:
                plan_result = self.llm.complete(plan_prompt)
                generated_plan = [
                    line.strip() for line in plan_result.text.strip().splitlines()
                    if line.strip().lower().startswith("week")
                ]
                if generated_plan:
                    posting_plan = generated_plan
            except Exception:
                pass

        return FinalOutput(
            strategy_summary=strategy_summary,
            content_concepts=top_ideas,
            hook_library=hooks,
            recommended_formats=formats,
            posting_experiment_plan=posting_plan,
            lineage_summary=lineage_summary,
        )
