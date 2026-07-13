"""Anthropic Claude provider -- for reasoning-heavy tasks."""

from __future__ import annotations

from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from app.llm.provider import LLMProvider

MAX_TOKENS = 4096


class ClaudeProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None, default_model: str) -> None:
        self._api_key = api_key
        self.default_model = default_model
        self._client: AsyncAnthropic | None = None

    @property
    def client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def complete(self, prompt: str, *, model: str | None = None) -> str:
        message = await self.client.messages.create(
            model=model or self.default_model,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in message.content if block.type == "text")

    async def stream(
        self, prompt: str, *, model: str | None = None
    ) -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model=model or self.default_model,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def is_configured(self) -> bool:
        return bool(self._api_key)
