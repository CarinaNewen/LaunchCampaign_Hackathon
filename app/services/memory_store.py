from __future__ import annotations

from copy import deepcopy
from threading import RLock

from app.models.schemas import AgentStatus, RunState, SwarmEvent, utc_now
from app.services.state_store import StateStore


class InMemoryStore(StateStore):
    """
    Dict-backed store for local development.
    Implements the same interface intended for RedisStore later.
    """

    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}
        self._lock = RLock()

    def create_run(self, run_state: RunState) -> RunState:
        with self._lock:
            self._runs[run_state.run_id] = deepcopy(run_state)
            return deepcopy(run_state)

    def get_run(self, run_id: str) -> RunState | None:
        with self._lock:
            run = self._runs.get(run_id)
            return deepcopy(run) if run else None

    def save_run(self, run_id: str, run_state: RunState) -> RunState:
        with self._lock:
            run_state.updated_at = utc_now()
            self._runs[run_id] = deepcopy(run_state)
            return deepcopy(run_state)

    def append_event(self, run_id: str, event: SwarmEvent) -> SwarmEvent:
        with self._lock:
            run = self._runs[run_id]
            run.event_history.append(event)
            run.updated_at = utc_now()
            return deepcopy(event)

    def update_agent_status(self, run_id: str, agent_name: str, status: AgentStatus) -> None:
        with self._lock:
            run = self._runs[run_id]
            run.agent_statuses[agent_name] = status
            run.updated_at = utc_now()
