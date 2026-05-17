from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel

from agents.aegis_agent import AegisAgent
from agents.hermes_agent import HermesAgent
from config import cfg
from core.orchestrator import Orchestrator
from memory.claude_obsidian import ClaudeObsidian
from memory.episodic import EpisodicMemory
from memory.qdrant_memory import QdrantMemory
from research.notebook_llm import NotebookLLM

app = FastAPI(title="AmaraOS API", version="0.2.0")

_orchestrator = Orchestrator()
_aegis = AegisAgent()
_hermes = HermesAgent()
_episodic = EpisodicMemory()
_qdrant = QdrantMemory()
_notebook = NotebookLLM()
_obsidian = ClaudeObsidian()


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
    response = await _orchestrator.run(req.prompt, session_id=req.session_id)
    return {"response": response}


# ------------------------------------------------------------------
# Agents
# ------------------------------------------------------------------

@app.post("/agent/aegis")
async def aegis_endpoint(req: AgentRequest) -> dict:
    response = _aegis.run(req.prompt)
    return {"agent": "aegis", "response": response}


@app.post("/agent/hermes")
async def hermes_endpoint(req: AgentRequest) -> dict:
    result = await _hermes.run_async(req.prompt, session_id=req.session_id)
    payload: dict = {"agent": "hermes", "route": result.route.value, "response": result.response}
    if result.sub_responses:
        payload["sub_responses"] = result.sub_responses
    return payload


# ------------------------------------------------------------------
# NotebookLLM (RAG)
# ------------------------------------------------------------------

@app.post("/notebook/ingest")
async def notebook_ingest(file: UploadFile = File(...)) -> dict:
    import tempfile, shutil, pathlib
    suffix = pathlib.Path(file.filename or "upload").suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    chunks = _notebook.ingest(tmp_path)
    return {"status": "ingested", "filename": file.filename, "chunks": chunks}


@app.post("/notebook/query")
async def notebook_query(req: NotebookQueryRequest) -> dict:
    answer = _notebook.query(req.question, k=req.k)
    return {"answer": answer}


# ------------------------------------------------------------------
# Obsidian
# ------------------------------------------------------------------

@app.post("/obsidian/search")
async def obsidian_search(req: NoteSearchRequest) -> dict:
    results = _obsidian.smart_search(req.query, limit=req.limit)
    return {"results": results}


@app.post("/obsidian/note")
async def obsidian_create_note(req: NoteRequest) -> dict:
    path = _obsidian.create_linked_note(req.title, req.context)
    return {"status": "created", "path": str(path)}


@app.get("/obsidian/analyze")
async def obsidian_analyze() -> dict:
    return _obsidian.analyze_vault()


@app.get("/obsidian/suggest/{note_title}")
async def obsidian_suggest(note_title: str) -> dict:
    suggestions = _obsidian.suggest_connections(note_title)
    return {"note": note_title, "related": suggestions}


# ------------------------------------------------------------------
# Qdrant vector memory
# ------------------------------------------------------------------

@app.post("/vector/search")
async def vector_search(req: VectorSearchRequest) -> dict:
    store = QdrantMemory(collection=req.collection)
    hits = store.search(req.query, k=req.k)
    return {"results": hits}


# ------------------------------------------------------------------
# Memory management
# ------------------------------------------------------------------

@app.delete("/memory/{session_id}")
async def delete_memory(session_id: str) -> dict:
    _episodic.clear(session_id)
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
