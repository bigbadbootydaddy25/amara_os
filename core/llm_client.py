from __future__ import annotations

import os
from typing import Any

import httpx

from config import cfg

_OLLAMA_TIMEOUT = 120.0


class AmaraLLM:
    """Ollama-first LLM client with optional Claude API fallback.

    All other modules import the `llm` singleton at the bottom of this file.
    """

    # ------------------------------------------------------------------
    # Sync inference
    # ------------------------------------------------------------------

    def chat(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        target = model or cfg.ollama_model
        try:
            return self._ollama_chat(prompt, system=system, model=target, temperature=temperature)
        except Exception as primary_err:
            if cfg.claude_api_key:
                try:
                    return self._claude_chat(prompt, system=system)
                except Exception:
                    pass
            raise RuntimeError(f"Ollama failed ({primary_err}) and no Claude fallback available")

    async def achat(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        target = model or cfg.ollama_model
        try:
            return await self._async_ollama_chat(prompt, system=system, model=target, temperature=temperature)
        except Exception as primary_err:
            if cfg.claude_api_key:
                try:
                    return await self._async_claude_chat(prompt, system=system)
                except Exception:
                    pass
            raise RuntimeError(f"Ollama failed ({primary_err}) and no Claude fallback available")

    def think(self, prompt: str, depth: int = 3) -> str:
        system = (
            f"You are Amara, an advanced reasoning AI. "
            f"Think carefully and thoroughly. Reasoning depth: {depth}/5."
        )
        return self.chat(prompt, system=system, temperature=0.3)

    def reason_fast(self, prompt: str) -> str:
        return self.chat(prompt, temperature=0.1)

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        resp = httpx.post(
            f"{cfg.ollama_base_url}/api/embeddings",
            json={"model": cfg.ollama_embed_model, "prompt": text},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    # ------------------------------------------------------------------
    # LangChain adapter
    # ------------------------------------------------------------------

    @property
    def langchain_llm(self) -> Any:
        try:
            from langchain_ollama import ChatOllama
            return ChatOllama(base_url=cfg.ollama_base_url, model=cfg.ollama_model)
        except ImportError:
            from langchain_community.chat_models import ChatOllama  # type: ignore[no-redef]
            return ChatOllama(base_url=cfg.ollama_base_url, model=cfg.ollama_model)

    # ------------------------------------------------------------------
    # Ollama internals
    # ------------------------------------------------------------------

    def _ollama_chat(
        self,
        prompt: str,
        system: str | None,
        model: str,
        temperature: float | None,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        resp = httpx.post(
            f"{cfg.ollama_base_url}/api/chat",
            json=payload,
            timeout=_OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    async def _async_ollama_chat(
        self,
        prompt: str,
        system: str | None,
        model: str,
        temperature: float | None,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False}
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        async with httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT) as client:
            resp = await client.post(f"{cfg.ollama_base_url}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]

    # ------------------------------------------------------------------
    # Claude fallback internals
    # ------------------------------------------------------------------

    def _claude_chat(self, prompt: str, system: str | None) -> str:
        from anthropic import Anthropic
        client = Anthropic(api_key=cfg.claude_api_key)
        kwargs: dict[str, Any] = {
            "model": cfg.claude_model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        msg = client.messages.create(**kwargs)
        return msg.content[0].text

    async def _async_claude_chat(self, prompt: str, system: str | None) -> str:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=cfg.claude_api_key)
        kwargs: dict[str, Any] = {
            "model": cfg.claude_model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        msg = await client.messages.create(**kwargs)
        return msg.content[0].text


llm = AmaraLLM()
