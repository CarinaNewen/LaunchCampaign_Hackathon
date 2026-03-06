from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.schemas import AgentActionResult, RunState


class BaseSwarmAgent(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def act(self, state: RunState) -> AgentActionResult:
        raise NotImplementedError
