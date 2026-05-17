from __future__ import annotations

import hashlib
import uuid
from typing import Any

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from config import cfg


class QdrantMemory:
    """Persistent semantic vector memory backed by Qdrant."""

    _VECTOR_SIZE = 768  # nomic-embed-text output dimension

    def __init__(self, collection: str = "amara_memory") -> None:
        self._collection = collection
        self._client = QdrantClient(
            host=cfg.qdrant_host,
            port=cfg.qdrant_port,
            api_key=cfg.qdrant_api_key or None,
            https=cfg.qdrant_use_https,
        )
        self._ensure_collection()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert(self, text: str, metadata: dict[str, Any] | None = None) -> str:
        """Embed text and upsert into the collection. Returns the point ID."""
        vector = self._embed(text)
        point_id = str(uuid.UUID(hashlib.md5(text.encode()).hexdigest()))
        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={"text": text, **(metadata or {})},
                )
            ],
        )
        return point_id

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Return top-k semantically similar records."""
        vector = self._embed(query)
        hits = self._client.search(
            collection_name=self._collection,
            query_vector=vector,
            limit=k,
        )
        return [{"text": h.payload.get("text", ""), "score": h.score, **h.payload} for h in hits]

    def delete_collection(self) -> None:
        self._client.delete_collection(self._collection)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_collection(self) -> None:
        existing = [c.name for c in self._client.get_collections().collections]
        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=self._VECTOR_SIZE, distance=Distance.COSINE),
            )

    def _embed(self, text: str) -> list[float]:
        resp = httpx.post(
            f"{cfg.ollama_base_url}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
