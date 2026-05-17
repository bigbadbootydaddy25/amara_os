from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any

from anthropic import Anthropic

from config import cfg


class Route(str, Enum):
    ORCHESTRATOR = "orchestrator"
    AEGIS = "aegis"
    NOTEBOOK = "notebook"
    OBSIDIAN = "obsidian"
    PARALLEL = "parallel"


@dataclass
class HermesResponse:
    route: Route
    response: str
    sub_responses: dict[str, str] | None = None


class HermesAgent:
    """Multi-agent dispatcher.

    Hermes classifies the intent of an incoming prompt and routes it to the
    most appropriate agent (or fans out to several in parallel, then
    synthesises a unified response).

    Routing targets
    ---------------
    - orchestrator  → general chat / knowledge retrieval (core.Orchestrator)
    - aegis         → memory-heavy reasoning / tool-use (agents.AegisAgent)
    - notebook      → document Q&A (research.NotebookLLM)
    - obsidian      → Obsidian vault operations (memory.ClaudeObsidian)
    - parallel      → all agents in parallel, responses merged by Claude
    """

    _CLASSIFY_PROMPT = """You are a routing assistant for AmaraOS.
Classify the user's intent into exactly one of these routes:
  orchestrator  – general conversation, knowledge retrieval, coding help
  aegis         – tasks requiring multi-step tool use or memory reasoning
  notebook      – questions answered from uploaded documents / PDFs
  obsidian      – create, search, or link notes in the Obsidian vault
  parallel      – the request is broad enough that multiple agents should answer

Respond with only the route name, lowercase. No explanation.

User prompt: {prompt}"""

    def __init__(self) -> None:
        self._claude = Anthropic(api_key=cfg.claude_api_key)

    # ------------------------------------------------------------------
    # Primary entry point
    # ------------------------------------------------------------------

    def run(self, prompt: str, session_id: str = "default") -> HermesResponse:
        route = self._classify(prompt)
        if route == Route.PARALLEL:
            return self._run_parallel(prompt, session_id)
        return HermesResponse(route=route, response=self._dispatch(route, prompt, session_id))

    async def run_async(self, prompt: str, session_id: str = "default") -> HermesResponse:
        route = self._classify(prompt)
        if route == Route.PARALLEL:
            return await self._run_parallel_async(prompt, session_id)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self._dispatch, route, prompt, session_id)
        return HermesResponse(route=route, response=response)

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify(self, prompt: str) -> Route:
        msg = self._claude.messages.create(
            model=cfg.claude_model,
            max_tokens=16,
            messages=[{
                "role": "user",
                "content": self._CLASSIFY_PROMPT.format(prompt=prompt),
            }],
        )
        raw = msg.content[0].text.strip().lower()
        try:
            return Route(raw)
        except ValueError:
            return Route.ORCHESTRATOR

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, route: Route, prompt: str, session_id: str) -> str:
        if route == Route.ORCHESTRATOR:
            from core.orchestrator import Orchestrator
            orch = Orchestrator()
            return asyncio.run(orch.run(prompt, session_id=session_id))

        if route == Route.AEGIS:
            from agents.aegis_agent import AegisAgent
            return AegisAgent().run(prompt)

        if route == Route.NOTEBOOK:
            from research.notebook_llm import NotebookLLM
            nb = NotebookLLM()
            return nb.query(prompt)

        if route == Route.OBSIDIAN:
            return self._handle_obsidian(prompt)

        return f"Unknown route: {route}"

    def _handle_obsidian(self, prompt: str) -> str:
        from memory.claude_obsidian import ClaudeObsidian
        co = ClaudeObsidian()
        lower = prompt.lower()
        if any(w in lower for w in ("create", "write", "new note", "add note")):
            # Extract title from prompt via Claude
            title = self._extract_title(prompt)
            path = co.create_linked_note(title, prompt)
            return f"Created note: {path}"
        if any(w in lower for w in ("connect", "link", "suggest", "related")):
            title = self._extract_title(prompt)
            suggestions = co.suggest_connections(title)
            return "Related notes:\n" + "\n".join(f"- {s}" for s in suggestions)
        if "analyze" in lower or "analyse" in lower or "map" in lower:
            analysis = co.analyze_vault()
            return (
                f"Vault: {analysis['note_count']} notes\n"
                f"Topics: {', '.join(analysis['topics'])}"
            )
        results = co.smart_search(prompt)
        if not results:
            return "No matching notes found."
        return "\n\n".join(f"**{r['title']}**\n{r['excerpt']}" for r in results)

    def _extract_title(self, prompt: str) -> str:
        msg = self._claude.messages.create(
            model=cfg.claude_model,
            max_tokens=32,
            messages=[{
                "role": "user",
                "content": f"Extract a short note title (3-6 words) from this request. Return only the title.\n\n{prompt}",
            }],
        )
        return msg.content[0].text.strip().strip('"').strip("'")

    # ------------------------------------------------------------------
    # Parallel fan-out
    # ------------------------------------------------------------------

    def _run_parallel(self, prompt: str, session_id: str) -> HermesResponse:
        targets = [Route.ORCHESTRATOR, Route.AEGIS, Route.NOTEBOOK]
        sub: dict[str, str] = {}
        for t in targets:
            try:
                sub[t.value] = self._dispatch(t, prompt, session_id)
            except Exception as exc:
                sub[t.value] = f"[error: {exc}]"
        merged = self._merge(prompt, sub)
        return HermesResponse(route=Route.PARALLEL, response=merged, sub_responses=sub)

    async def _run_parallel_async(self, prompt: str, session_id: str) -> HermesResponse:
        loop = asyncio.get_event_loop()
        targets = [Route.ORCHESTRATOR, Route.AEGIS, Route.NOTEBOOK]

        async def _run_one(route: Route) -> tuple[str, str]:
            try:
                resp = await loop.run_in_executor(None, self._dispatch, route, prompt, session_id)
                return route.value, resp
            except Exception as exc:
                return route.value, f"[error: {exc}]"

        results = await asyncio.gather(*[_run_one(t) for t in targets])
        sub = dict(results)
        merged = self._merge(prompt, sub)
        return HermesResponse(route=Route.PARALLEL, response=merged, sub_responses=sub)

    def _merge(self, original_prompt: str, sub: dict[str, str]) -> str:
        responses_block = "\n\n".join(
            f"[{name}]:\n{text}" for name, text in sub.items()
        )
        msg = self._claude.messages.create(
            model=cfg.claude_model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": (
                    f"Original question: {original_prompt}\n\n"
                    f"Multiple agents responded:\n\n{responses_block}\n\n"
                    "Synthesise these into a single, coherent answer."
                ),
            }],
        )
        return msg.content[0].text.strip()
