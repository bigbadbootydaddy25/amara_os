"""Provider-agnostic LLM interface.

FOREMAN calls providers through this interface only -- it never talks to
Ollama or Anthropic directly. `stream` exists from Phase 1 on so the
Phase 2 presence layer (ElevenLabs streaming TTS, HeyGen LiveAvatar
text_stream) has something to consume; Phase 1 callers only use `complete`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(self, prompt: str, *, model: str | None = None) -> str:
        """Return the full completion for `prompt`."""

    @abstractmethod
    async def stream(
        self, prompt: str, *, model: str | None = None
    ) -> AsyncIterator[str]:
        """Yield incremental text chunks for `prompt`."""
        raise NotImplementedError
        yield ""  # pragma: no cover - makes this an async generator signature
