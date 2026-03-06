from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import CampaignInput, RunState, SwarmRunRequest
from app.services.llm import LLMService
from app.services.memory_store import InMemoryStore
from app.services.swarm_engine import SwarmEngine

router = APIRouter(prefix="/swarm", tags=["swarm"])

store = InMemoryStore()
llm = LLMService()
engine = SwarmEngine(store=store, llm=llm)


@router.post("/run", response_model=RunState)
def create_swarm_run(payload: SwarmRunRequest) -> RunState:
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
