"""AMARA OS FastAPI entry point. Local only -- run with:

    uvicorn app.main:app
"""

from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import FastAPI, HTTPException

from app.config import Settings, get_settings
from app.foreman.router import Foreman, ForemanTaskRejected
from app.foreman.tasks import OutcomePatchRequest, TaskRequest, TaskResult
from app.llm import build_providers
from app.memory.client import get_supabase_client
from app.memory.outcome_log import OutcomeLogStore

logger = logging.getLogger("amara_os")

app = FastAPI(title="AMARA OS", version="0.1.0")


@lru_cache
def get_foreman() -> Foreman:
    settings = get_settings()
    providers = build_providers(settings)
    client = get_supabase_client(settings)
    outcome_store = OutcomeLogStore(client)
    return Foreman(
        settings=settings,
        providers=providers,
        outcome_store=outcome_store,
        embedder=providers["ollama"],
    )


@app.get("/health")
async def health() -> dict:
    settings: Settings = get_settings()
    providers = build_providers(settings)
    ollama_reachable = await providers["ollama"].is_reachable()
    return {
        "app": settings.app.name,
        "phase": settings.app.phase,
        "workspaces": settings.workspaces,
        "clients": [c.id for c in settings.clients if c.active],
        "providers": {
            "ollama": {"reachable": ollama_reachable, "base_url": providers["ollama"].base_url},
            "anthropic": {"key_present": providers["anthropic"].is_configured()},
        },
    }


@app.post("/tasks", response_model=TaskResult)
async def submit_task(request: TaskRequest) -> TaskResult:
    foreman = get_foreman()
    try:
        return await foreman.run_task(
            workspace=request.workspace,
            task_type=request.task_type,
            payload=request.payload,
        )
    except ForemanTaskRejected as rejected:
        logger.warning("output filter rejected task_type=%s: %s", request.task_type, rejected)
        raise HTTPException(status_code=422, detail=str(rejected)) from rejected


@app.patch("/outcomes/{outcome_id}")
async def patch_outcome(outcome_id: str, patch: OutcomePatchRequest) -> dict:
    settings = get_settings()
    client = get_supabase_client(settings)
    outcome_store = OutcomeLogStore(client)
    return outcome_store.patch(
        outcome_id,
        outcome_status=patch.outcome_status,
        outcome=patch.outcome,
        correction=patch.correction,
    )
