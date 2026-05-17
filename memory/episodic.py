from __future__ import annotations

from typing import Any

from mem0 import MemoryClient

from config import cfg


class EpisodicMemory:
    def __init__(self) -> None:
        self._client = MemoryClient(api_key=cfg.mem0_api_key)

    def store(self, prompt: str, response: str, session_id: str = "default") -> None:
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": response},
        ]
        self._client.add(messages, user_id=session_id)

    def recall(self, query: str, session_id: str = "default", limit: int = 5) -> list[dict[str, Any]]:
        results = self._client.search(query, user_id=session_id, limit=limit)
        return [
            {"role": r.get("role", "user"), "content": r.get("memory", "")}
            for r in results
        ]

    def clear(self, session_id: str) -> None:
        self._client.delete_all(user_id=session_id)
