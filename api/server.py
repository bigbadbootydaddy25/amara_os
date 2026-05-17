from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agents.aegis_agent import AegisAgent
from config import cfg
from core.orchestrator import Orchestrator
from memory.episodic import EpisodicMemory

app = FastAPI(title="AmaraOS API", version="0.1.0")

_orchestrator = Orchestrator()
_agent = AegisAgent()
_episodic = EpisodicMemory()


class RunRequest(BaseModel):
    prompt: str
    session_id: str = "default"


class AgentRequest(BaseModel):
    prompt: str


@app.post("/run")
async def run_endpoint(req: RunRequest) -> dict:
    response = await _orchestrator.run(req.prompt, session_id=req.session_id)
    return {"response": response}


@app.post("/agent")
async def agent_endpoint(req: AgentRequest) -> dict:
    response = _agent.run(req.prompt)
    return {"response": response}


@app.delete("/memory/{session_id}")
async def delete_memory(session_id: str) -> dict:
    _episodic.clear(session_id)
    return {"status": "cleared", "session_id": session_id}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=cfg.api_host, port=cfg.api_port)
