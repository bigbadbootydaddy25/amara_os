from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel

from config import cfg

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Lazy singleton registry
# ------------------------------------------------------------------

_singletons: dict[str, Any] = {}


def _get(name: str, factory: Any) -> Any:
    if name not in _singletons:
        try:
            _singletons[name] = factory()
        except Exception as exc:
            logger.warning("Failed to initialise %s: %s", name, exc)
            raise HTTPException(status_code=503, detail=f"{name} unavailable: {exc}")
    return _singletons[name]


# ------------------------------------------------------------------
# App lifecycle
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    logger.info("AmaraOS API starting")
    yield
    logger.info("AmaraOS API shutting down")


app = FastAPI(title="AmaraOS API", version="0.2.0", lifespan=lifespan)


# ------------------------------------------------------------------
# Request / response models
# ------------------------------------------------------------------

class RunRequest(BaseModel):
    prompt: str
    session_id: str = "default"


class AgentRequest(BaseModel):
    prompt: str
    session_id: str = "default"


class NoteRequest(BaseModel):
    title: str
    context: str


class NoteSearchRequest(BaseModel):
    query: str
    limit: int = 8


class NotebookQueryRequest(BaseModel):
    question: str
    k: int = 5


class VectorSearchRequest(BaseModel):
    query: str
    k: int = 5
    collection: str = "amara_memory"


# ------------------------------------------------------------------
# Core orchestrator
# ------------------------------------------------------------------

@app.post("/run")
async def run_endpoint(req: RunRequest) -> dict:
    from core.orchestrator import Orchestrator
    orch = _get("orchestrator", Orchestrator)
    response = await orch.run(req.prompt, session_id=req.session_id)
    return {"response": response}


# ------------------------------------------------------------------
# Agents
# ------------------------------------------------------------------

@app.post("/agent/aegis")
async def aegis_endpoint(req: AgentRequest) -> dict:
    from agents.aegis_agent import AegisAgent
    agent = _get("aegis", AegisAgent)
    response = agent.run(req.prompt)
    return {"agent": "aegis", "response": response}


@app.post("/agent/hermes")
async def hermes_endpoint(req: AgentRequest) -> dict:
    from agents.hermes_agent import HermesAgent
    agent = _get("hermes", HermesAgent)
    result = await agent.run_async(req.prompt, session_id=req.session_id)
    payload: dict = {"agent": "hermes", "route": result.route.value, "response": result.response}
    if result.sub_responses:
        payload["sub_responses"] = result.sub_responses
    return payload


# ------------------------------------------------------------------
# NotebookLLM (RAG)
# ------------------------------------------------------------------

@app.post("/notebook/ingest")
async def notebook_ingest(file: UploadFile = File(...)) -> dict:
    import pathlib
    import shutil
    import tempfile
    from research.notebook_llm import NotebookLLM
    nb = _get("notebook", NotebookLLM)
    suffix = pathlib.Path(file.filename or "upload").suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    chunks = nb.ingest(tmp_path)
    return {"status": "ingested", "filename": file.filename, "chunks": chunks}


@app.post("/notebook/query")
async def notebook_query(req: NotebookQueryRequest) -> dict:
    from research.notebook_llm import NotebookLLM
    nb = _get("notebook", NotebookLLM)
    answer = nb.query(req.question, k=req.k)
    return {"answer": answer}


# ------------------------------------------------------------------
# Obsidian
# ------------------------------------------------------------------

@app.post("/obsidian/search")
async def obsidian_search(req: NoteSearchRequest) -> dict:
    from memory.claude_obsidian import ClaudeObsidian
    co = _get("obsidian", ClaudeObsidian)
    results = co.smart_search(req.query, limit=req.limit)
    return {"results": results}


@app.post("/obsidian/note")
async def obsidian_create_note(req: NoteRequest) -> dict:
    from memory.claude_obsidian import ClaudeObsidian
    co = _get("obsidian", ClaudeObsidian)
    path = co.create_linked_note(req.title, req.context)
    return {"status": "created", "path": str(path)}


@app.get("/obsidian/analyze")
async def obsidian_analyze() -> dict:
    from memory.claude_obsidian import ClaudeObsidian
    co = _get("obsidian", ClaudeObsidian)
    return co.analyze_vault()


@app.get("/obsidian/suggest/{note_title}")
async def obsidian_suggest(note_title: str) -> dict:
    from memory.claude_obsidian import ClaudeObsidian
    co = _get("obsidian", ClaudeObsidian)
    suggestions = co.suggest_connections(note_title)
    return {"note": note_title, "related": suggestions}


# ------------------------------------------------------------------
# Qdrant vector memory
# ------------------------------------------------------------------

@app.post("/vector/search")
async def vector_search(req: VectorSearchRequest) -> dict:
    from memory.qdrant_memory import QdrantMemory
    store = QdrantMemory(collection=req.collection)
    hits = store.search(req.query, k=req.k)
    return {"results": hits}


# ------------------------------------------------------------------
# Memory management
# ------------------------------------------------------------------

@app.delete("/memory/{session_id}")
async def delete_memory(session_id: str) -> dict:
    from memory.episodic import EpisodicMemory
    episodic = _get("episodic", EpisodicMemory)
    episodic.clear(session_id)
    return {"status": "cleared", "session_id": session_id}


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.2.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=cfg.api_host, port=cfg.api_port)
