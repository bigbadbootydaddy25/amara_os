from __future__ import annotations

from core.llm_client import llm


class Router:
    async def route(self, prompt: str) -> str:
        return await llm.achat(prompt)
