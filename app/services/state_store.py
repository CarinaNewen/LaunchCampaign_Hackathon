from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.schemas import AgentStatus, RunState, SwarmEvent


class StateStore(ABC):
    @abstractmethod
    def create_run(self, run_state: RunState) -> RunState:
        raise NotImplementedError

    @abstractmethod
    def get_run(self, run_id: str) -> RunState | None:
        raise NotImplementedError

    @abstractmethod
    def save_run(self, run_id: str, run_state: RunState) -> RunState:
        raise NotImplementedError

    @abstractmethod
    def append_event(self, run_id: str, event: SwarmEvent) -> SwarmEvent:
        raise NotImplementedError

    @abstractmethod
    def update_agent_status(self, run_id: str, agent_name: str, status: AgentStatus) -> None:
        raise NotImplementedError
