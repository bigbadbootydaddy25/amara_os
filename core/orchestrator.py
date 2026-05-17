from __future__ import annotations

import asyncio
from typing import Optional

from config import cfg
from core.router import Router
from memory.episodic import EpisodicMemory
from memory.graph_memory import GraphMemory
from observability.tracer import Tracer


class Orchestrator:
    def __init__(self) -> None:
        self.router = Router()
        self.episodic = EpisodicMemory()
        self.graph = GraphMemory()
        self.tracer = Tracer()

    async def run(self, prompt: str, session_id: str = "default") -> str:
        with self.tracer.trace(name="orchestrator.run", session_id=session_id):
            context = self.episodic.recall(prompt, session_id=session_id)
            graph_ctx = self.graph.retrieve(prompt)

            augmented = self._build_prompt(prompt, context, graph_ctx)

            with self.tracer.span("router.route"):
                response = await self.router.route(augmented)

            self.episodic.store(prompt, response, session_id=session_id)
            self.graph.upsert(prompt, response)

        return response

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
