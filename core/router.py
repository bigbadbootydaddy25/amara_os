from __future__ import annotations

import httpx
from anthropic import AsyncAnthropic

from config import cfg


class Router:
    def __init__(self) -> None:
        self._claude = AsyncAnthropic(api_key=cfg.claude_api_key)

    async def route(self, prompt: str) -> str:
        try:
            return await self._ollama(prompt)
        except Exception:
            return await self._claude_fallback(prompt)

    async def _ollama(self, prompt: str) -> str:
        url = f"{cfg.ollama_base_url}/api/generate"
        payload = {"model": cfg.ollama_model, "prompt": prompt, "stream": False}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()["response"]

    async def _claude_fallback(self, prompt: str) -> str:
        msg = await self._claude.messages.create(
            model=cfg.claude_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
