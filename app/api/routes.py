from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import AgentStatus, CampaignInput, RunState, SwarmRunRequest
from app.services.llm import LLMService
from app.services.memory_store import InMemoryStore
from app.services.swarm_engine import SwarmEngine

router = APIRouter(prefix="/swarm", tags=["swarm"])

store = InMemoryStore()
llm = LLMService()
engine = SwarmEngine(store=store, llm=llm)


@router.post("/start", response_model=RunState)
def start_swarm_run(payload: SwarmRunRequest) -> RunState:
    """Create a run and return its run_id immediately (before rounds execute)."""
    return engine.start_run(payload.campaign_input)


@router.post("/run/{run_id}", response_model=RunState)
def execute_swarm_run(run_id: str, payload: SwarmRunRequest) -> RunState:
    """Execute rounds for an already-created run."""
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return engine.run_rounds(run_id, payload.max_rounds)


@router.post("/run", response_model=RunState)
def create_swarm_run(payload: SwarmRunRequest) -> RunState:
    """Legacy single-call endpoint: create + execute in one request."""
    run = engine.start_run(payload.campaign_input)
    return engine.run_rounds(run.run_id, payload.max_rounds)


@router.get("/run/{run_id}", response_model=RunState)
def get_swarm_run(run_id: str) -> RunState:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/demo", response_model=RunState)
def demo_run() -> RunState:
    demo = SwarmRunRequest(
        campaign_input=CampaignInput(
            product_info="Hydration electrolyte gummies",
            target_audience="busy fitness-focused professionals",
            creator_profile="micro fitness creator with educational storytelling style",
            platform="TikTok",
            global_trends=["day-in-the-life", "micro-habits"],
            niche_trends=["hydration challenge", "pre-workout stacks"],
            viral_examples=["before/after routine cuts", "POV confession hooks"],
        ),
        max_rounds=3,
    )
    run = engine.start_run(demo.campaign_input)
    return engine.run_rounds(run.run_id, demo.max_rounds)


@router.post("/run/{run_id}/kill/{agent_name}", response_model=RunState)
def kill_agent(run_id: str, agent_name: str) -> RunState:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    known = {a.name for a in engine.agents}
    if agent_name not in known:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent_name}")
    if run.agent_statuses.get(agent_name) == AgentStatus.done:
        raise HTTPException(status_code=409, detail="Agent has already completed this round.")
    store.kill_agent(run_id, agent_name)
    updated = store.get_run(run_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Run not found after kill")
    return updated


@router.get("/llm/health")
def llm_health() -> dict[str, object]:
    return llm.health()


@router.post("/llm/test")
def llm_test(prompt: str = "Generate 3 hooks for a short-form social video.") -> dict[str, object]:
    result = llm.complete(prompt)
    return {
        "provider": result.provider,
        "model": result.model,
        "text": result.text,
        "raw": result.raw,
    }
