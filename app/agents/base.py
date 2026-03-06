from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.schemas import AgentActionResult, RunState


class BaseSwarmAgent(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def act(self, state: RunState) -> AgentActionResult:
        raise NotImplementedError

    @abstractmethod
    def can_act(self, state: RunState) -> bool:
        """Return True only when this agent has meaningful work to do."""
        raise NotImplementedError

    def priority(self, state: RunState) -> float:  # noqa: ARG002
        """Higher = acts sooner when multiple agents are ready.
        Subclasses override to make scheduling state-driven."""
        return 0.5

    def _parse_lines(self, content: str) -> dict[str, str]:
        """Parse TITLE/DESCRIPTION/HOOK/CONFIDENCE/SCORES lines from LLM output."""
        parsed: dict[str, str] = {}
        for line in content.splitlines():
            cleaned = line.strip()
            upper = cleaned.upper()
            if upper.startswith("TITLE:"):
                parsed["title"] = cleaned.split(":", 1)[1].strip()
            elif upper.startswith("DESCRIPTION:"):
                parsed["description"] = cleaned.split(":", 1)[1].strip()
            elif upper.startswith("HOOK:"):
                parsed["hook"] = cleaned.split(":", 1)[1].strip()
            elif upper.startswith("CONFIDENCE:"):
                raw = cleaned.split(":", 1)[1].strip()
                try:
                    parsed["confidence"] = str(max(0.4, min(0.95, float(raw))))
                except ValueError:
                    pass
            elif upper.startswith("SCORES:"):
                parsed["scores"] = cleaned.split(":", 1)[1].strip()
        return parsed
