from __future__ import annotations

import os
from copy import deepcopy
from threading import RLock

from app.models.schemas import AgentStatus, RunState, SwarmEvent, utc_now
from app.services.state_store import StateStore

# Runs are persisted here so a server restart can recover in-flight state.
_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "run_snapshots")


class InMemoryStore(StateStore):
    """
    Dict-backed store for local development.
    Writes a JSON snapshot to disk on every save so the swarm survives server restarts.
    Implements the same interface intended for RedisStore later.
    """

    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}
        self._lock = RLock()
        os.makedirs(_PERSIST_DIR, exist_ok=True)

    # ── Write ─────────────────────────────────────────────────────────────────

    def create_run(self, run_state: RunState) -> RunState:
        with self._lock:
            self._runs[run_state.run_id] = deepcopy(run_state)
            self._persist(run_state)
            return deepcopy(run_state)

    def save_run(self, run_id: str, run_state: RunState) -> RunState:
        with self._lock:
            run_state.updated_at = utc_now()
            self._runs[run_id] = deepcopy(run_state)
            self._persist(run_state)
            return deepcopy(run_state)

    def append_event(self, run_id: str, event: SwarmEvent) -> SwarmEvent:
        with self._lock:
            run = self._runs[run_id]
            run.event_history.append(event)
            run.updated_at = utc_now()
            self._persist(run)
            return deepcopy(event)

    def update_agent_status(self, run_id: str, agent_name: str, status: AgentStatus) -> None:
        with self._lock:
            run = self._runs[run_id]
            run.agent_statuses[agent_name] = status
            run.updated_at = utc_now()

    def kill_agent(self, run_id: str, agent_name: str) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(f"Run {run_id} not found.")
            if agent_name not in run.killed_agents:
                run.killed_agents.append(agent_name)
            run.agent_statuses[agent_name] = AgentStatus.failed
            run.updated_at = utc_now()
            self._persist(run)

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> RunState | None:
        with self._lock:
            if run_id in self._runs:
                return deepcopy(self._runs[run_id])
            # Crash-recovery: try to restore from disk snapshot
            run = self._restore(run_id)
            if run is not None:
                self._runs[run_id] = run
                return deepcopy(run)
            return None

    # ── Persistence helpers ───────────────────────────────────────────────────

    def _persist(self, run: RunState) -> None:
        """Write a JSON snapshot to disk. Silently swallows I/O errors."""
        try:
            path = os.path.join(_PERSIST_DIR, f"{run.run_id}.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(run.model_dump_json())
        except Exception:
            pass

    def _restore(self, run_id: str) -> RunState | None:
        """Attempt to load a run from a disk snapshot. Returns None on any error."""
        try:
            path = os.path.join(_PERSIST_DIR, f"{run_id}.json")
            if not os.path.exists(path):
                return None
            with open(path, encoding="utf-8") as fh:
                return RunState.model_validate_json(fh.read())
        except Exception:
            return None
