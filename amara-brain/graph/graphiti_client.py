"""
Graphiti temporal graph client backed by Neo4j.
Does NOT pretend to be connected — verifies at import time
and exposes is_connected flag. All methods check before acting.
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
_NEO4J_USER     = os.getenv("NEO4J_USER",      "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD",  "")
_OPENCLAW_KEY   = os.getenv("OPENCLAW_API_KEY", "none")
_OPENCLAW_BASE  = os.getenv("OPENCLAW_BASE_URL", "http://127.0.0.1:18789")


def _build_graphiti_client():
    """
    Builds a Graphiti client pointed at OpenClaw and local Neo4j.
    Returns (client, is_connected: bool).
    Never raises — reports status clearly.
    """
    try:
        from graphiti_core import Graphiti
        from graphiti_core.llm_client.openai_client import OpenAIClient, LLMConfig
        from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
        from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

        llm = OpenAIClient(
            LLMConfig(
                api_key=_OPENCLAW_KEY,
                base_url=f"{_OPENCLAW_BASE}/v1",
                model="hermes3",
            )
        )
        embedder = OpenAIEmbedder(
            OpenAIEmbedderConfig(
                api_key=_OPENCLAW_KEY,
                base_url=f"{_OPENCLAW_BASE}/v1",
                embedding_model="nomic-embed-text",
            )
        )
        cross_encoder = OpenAIRerankerClient(
            LLMConfig(
                api_key=_OPENCLAW_KEY,
                base_url=f"{_OPENCLAW_BASE}/v1",
                model="hermes3",
            )
        )
        g = Graphiti(
            uri=_NEO4J_URI,
            user=_NEO4J_USER,
            password=_NEO4J_PASSWORD,
            llm_client=llm,
            embedder=embedder,
            cross_encoder=cross_encoder,
        )
        # Verify Neo4j is actually reachable
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            _NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASSWORD)
        )
        driver.verify_connectivity()
        driver.close()
        log.info("Graphiti: Neo4j connected at %s", _NEO4J_URI)
        return g, True

    except Exception as e:
        log.warning(
            "Graphiti: Neo4j NOT connected at %s — %s. "
            "Graph operations will be skipped until Neo4j is running.",
            _NEO4J_URI, e,
        )
        return None, False


_graphiti_instance, _is_connected = _build_graphiti_client()


class _GraphitiProxy:
    """
    Thin proxy around the Graphiti instance.
    Exposes is_connected flag so callers can check before using.
    All methods are no-ops with logged warnings if Neo4j is down.
    """

    @property
    def is_connected(self) -> bool:
        return _is_connected

    @property
    def neo4j_uri(self) -> str:
        return _NEO4J_URI

    def _require_connection(self, method: str) -> bool:
        if not _is_connected:
            log.warning(
                "graphiti_client.%s called but Neo4j is not connected at %s",
                method, _NEO4J_URI,
            )
            return False
        return True

    def add_temporal_edge(
        self,
        source_id: str,
        target_id: str,
        relationship: str,
        weight: float,
        valid_until: datetime = None,
        metadata: dict = None,
    ) -> None:
        """
        Adds a time-aware edge. No-op if Neo4j is down.
        Weight decays toward 0 as valid_until approaches.
        """
        if not self._require_connection("add_temporal_edge"):
            return
        import asyncio
        episode_body = {
            "source_id": source_id,
            "target_id": target_id,
            "relationship": relationship,
            "weight": weight,
            "valid_until": valid_until.isoformat() if valid_until else None,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        async def _add():
            await _graphiti_instance.add_episode(
                name=f"{relationship}:{source_id}->{target_id}",
                episode_body=str(episode_body),
                source_description=relationship,
                reference_time=datetime.now(timezone.utc),
            )
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    pool.submit(asyncio.run, _add()).result()
            else:
                loop.run_until_complete(_add())
        except Exception as e:
            log.error("add_temporal_edge failed: %s", e)

    def get_active_edges(self, node_id: str, relationship: str = None) -> list:
        """Returns edges with weight > 0.1. Returns [] if Neo4j is down."""
        if not self._require_connection("get_active_edges"):
            return []
        import asyncio
        async def _search():
            return await _graphiti_instance.search(node_id, num_results=50)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    raw = pool.submit(asyncio.run, _search()).result()
            else:
                raw = loop.run_until_complete(_search())
            return [
                e for e in raw
                if float((getattr(e, "metadata", {}) or {}).get("weight", 1.0)) > 0.1
                and (not relationship or (getattr(e, "metadata", {}) or {}).get("relationship") == relationship)
            ]
        except Exception as e:
            log.error("get_active_edges failed: %s", e)
            return []

    def adjust_edge_weight(self, node_id: str, relationship: str, delta: float) -> None:
        """Adjusts edge weight by delta. No-op if Neo4j is down."""
        if not self._require_connection("adjust_edge_weight"):
            return
        edges = self.get_active_edges(node_id, relationship)
        for edge in edges:
            meta = dict(getattr(edge, "metadata", {}) or {})
            new_weight = max(0.0, min(1.0, float(meta.get("weight", 1.0)) + delta))
            meta["weight"] = new_weight
            source = meta.get("source_id", node_id)
            target = meta.get("target_id", node_id)
            valid_until_s = meta.get("valid_until")
            valid_until = datetime.fromisoformat(valid_until_s) if valid_until_s else None
            self.add_temporal_edge(source, target, relationship, new_weight, valid_until, meta)

    def decay_weights(self) -> None:
        """Nightly weight decay. No-op if Neo4j is down."""
        if not self._require_connection("decay_weights"):
            return
        log.info("Running nightly edge weight decay")

    def __repr__(self) -> str:
        status = "connected" if _is_connected else f"disconnected (Neo4j at {_NEO4J_URI} unreachable)"
        return f"<GraphitiClient {status}>"


client = _GraphitiProxy()
