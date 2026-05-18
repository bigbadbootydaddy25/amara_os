from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from core.llm_client import llm

logger = logging.getLogger(__name__)


@contextmanager
def _noop_span(_name: str) -> Generator[None, None, None]:
    yield


class Orchestrator:
    def __init__(self) -> None:
        self._episodic = None
        self._graph = None
        self._tracer = None
        self._init_services()

    def _init_services(self) -> None:
        try:
            from memory.episodic import EpisodicMemory
            self._episodic = EpisodicMemory()
        except Exception as exc:
            logger.warning("EpisodicMemory unavailable: %s", exc)

        try:
            from memory.graph_memory import GraphMemory
            self._graph = GraphMemory()
        except Exception as exc:
            logger.warning("GraphMemory unavailable: %s", exc)

        try:
            from observability.tracer import Tracer
            self._tracer = Tracer()
        except Exception as exc:
            logger.warning("Tracer unavailable: %s", exc)

    async def run(self, prompt: str, session_id: str = "default") -> str:
        trace_ctx = (
            self._tracer.trace(name="orchestrator.run", session_id=session_id)
            if self._tracer
            else _noop_span("orchestrator.run")
        )
        with trace_ctx:
            context = self._recall(prompt, session_id)
            graph_ctx = self._graph_retrieve(prompt)
            augmented = self._build_prompt(prompt, context, graph_ctx)

            span_ctx = (
                self._tracer.span("router.route")
                if self._tracer
                else _noop_span("router.route")
            )
            with span_ctx:
                response = await llm.achat(augmented)

            self._store(prompt, response, session_id)
            self._graph_upsert(prompt, response)

        return response

    # ------------------------------------------------------------------
    # Safe wrappers around optional services
    # ------------------------------------------------------------------

    def _recall(self, prompt: str, session_id: str) -> list[dict]:
        if self._episodic is None:
            return []
        try:
            return self._episodic.recall(prompt, session_id=session_id)
        except Exception as exc:
            logger.warning("EpisodicMemory.recall failed: %s", exc)
            return []

    def _store(self, prompt: str, response: str, session_id: str) -> None:
        if self._episodic is None:
            return
        try:
            self._episodic.store(prompt, response, session_id=session_id)
        except Exception as exc:
            logger.warning("EpisodicMemory.store failed: %s", exc)

    def _graph_retrieve(self, prompt: str) -> list[dict]:
        if self._graph is None:
            return []
        try:
            return self._graph.retrieve(prompt)
        except Exception as exc:
            logger.warning("GraphMemory.retrieve failed: %s", exc)
            return []

    def _graph_upsert(self, prompt: str, response: str) -> None:
        if self._graph is None:
            return
        try:
            self._graph.upsert(prompt, response)
        except Exception as exc:
            logger.warning("GraphMemory.upsert failed: %s", exc)

    # ------------------------------------------------------------------
    # Prompt assembly
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        prompt: str,
        episodic_ctx: list[dict],
        graph_ctx: list[dict],
    ) -> str:
        parts: list[str] = []

        if episodic_ctx:
            mem_block = "\n".join(
                f"- [{m.get('role','user')}]: {m.get('content','')}"
                for m in episodic_ctx
            )
            parts.append(f"Relevant memory:\n{mem_block}")

        if graph_ctx:
            graph_block = "\n".join(
                f"- {n.get('prompt','')} → {n.get('response','')}"
                for n in graph_ctx
            )
            parts.append(f"Knowledge graph context:\n{graph_block}")

        parts.append(prompt)
        return "\n\n".join(parts)
