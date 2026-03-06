from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


class AgentStatus(str, Enum):
    idle = "idle"
    running = "running"
    done = "done"
    failed = "failed"


class AgentActionType(str, Enum):
    propose = "propose"
    critique = "critique"
    mutate = "mutate"
    merge = "merge"
    score = "score"
    finalize = "finalize"


class CampaignInput(BaseModel):
    product_info: str
    target_audience: str
    creator_profile: str
    platform: str
    global_trends: list[str] = Field(default_factory=list)
    niche_trends: list[str] = Field(default_factory=list)
    viral_examples: list[str] = Field(default_factory=list)


class Idea(BaseModel):
    idea_id: str = Field(default_factory=lambda: new_id("idea"))
    title: str
    description: str
    hook: str
    source_agent: str
    parent_idea_ids: list[str] = Field(default_factory=list)
    round_created: int = 0
    confidence: float = 0.5
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SwarmEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: new_id("evt"))
    run_id: str
    agent_name: str
    round_number: int
    action_type: AgentActionType
    message: str
    idea_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class FinalOutput(BaseModel):
    strategy_summary: str = ""
    content_concepts: list[Idea] = Field(default_factory=list)
    hook_library: list[str] = Field(default_factory=list)
    recommended_formats: list[str] = Field(default_factory=list)
    posting_experiment_plan: list[str] = Field(default_factory=list)
    lineage_summary: list[str] = Field(default_factory=list)


class RunState(BaseModel):
    run_id: str = Field(default_factory=lambda: new_id("run"))
    campaign_input: CampaignInput
    ideas: list[Idea] = Field(default_factory=list)
    event_history: list[SwarmEvent] = Field(default_factory=list)
    agent_statuses: dict[str, AgentStatus] = Field(default_factory=dict)
    killed_agents: list[str] = Field(default_factory=list)
    round_number: int = 0
    scores: dict[str, float] = Field(default_factory=dict)
    confidence: dict[str, float] = Field(default_factory=dict)
    lineage: dict[str, list[str]] = Field(default_factory=dict)
    # peer_votes: all score votes cast by any agent for each idea; final score = mean
    peer_votes: dict[str, list[float]] = Field(default_factory=dict)
    # agent_fail_counts: tracks consecutive failures; at 2 the agent is auto-killed
    agent_fail_counts: dict[str, int] = Field(default_factory=dict)
    final_output: FinalOutput | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SwarmRunRequest(BaseModel):
    campaign_input: CampaignInput
    max_rounds: int = Field(default=3, ge=1, le=6)


class AgentActionResult(BaseModel):
    action_type: AgentActionType
    message: str
    new_ideas: list[Idea] = Field(default_factory=list)
    updated_scores: dict[str, float] = Field(default_factory=dict)
    updated_confidence: dict[str, float] = Field(default_factory=dict)
    lineage_updates: dict[str, list[str]] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
