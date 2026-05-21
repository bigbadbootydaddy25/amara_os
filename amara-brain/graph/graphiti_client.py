"""
Graphiti temporal graph client.
Every relationship has a timestamp and weight that decays over time.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from graphiti_core import Graphiti
from graphiti_core.llm_client.openai_client import OpenAIClient, LLMConfig
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

_NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
_NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
_OPENCLAW_KEY = os.getenv("OPENCLAW_API_KEY", "none")

_llm_client = OpenAIClient(
    LLMConfig(
        api_key=_OPENCLAW_KEY,
        base_url="http://127.0.0.1:18789/v1",
        model="hermes3",
    )
)

_embedder = OpenAIEmbedder(
    OpenAIEmbedderConfig(
        api_key=_OPENCLAW_KEY,
        base_url="http://127.0.0.1:18789/v1",
        embedding_model="nomic-embed-text",
    )
)

_cross_encoder = OpenAIRerankerClient(
    LLMConfig(
        api_key=_OPENCLAW_KEY,
        base_url="http://127.0.0.1:18789/v1",
        model="hermes3",
    )
)

client = Graphiti(
    uri=_NEO4J_URI,
    user=_NEO4J_USER,
    password=_NEO4J_PASSWORD,
    llm_client=_llm_client,
    embedder=_embedder,
    cross_encoder=_cross_encoder,
)

_OBSIDIAN_PATH = Path("/Users/user/obsidian-vault/amara/graph")
_INACTIVE_WEIGHT_THRESHOLD = 0.1


def add_temporal_edge(
    source_id: str,
    target_id: str,
    relationship: str,
    weight: float,
    valid_until: datetime = None,
    metadata: dict = None,
) -> None:
    """
    Adds a time-aware edge to the graph.
    Weight decays toward 0 as valid_until approaches.
    Edge is considered inactive when weight < 0.1.

    Operator locked with supplier:
      valid_until = lock expiry; weight starts 1.0, decays to 0 by expiry.
      Harvey alerts on weight < 0.2 (auto-resume signal).

    Supplier reliability:
      Missed delivery: -0.15 | On-time: +0.05
      Blacklist filed at weight < 0.3

    Driver performance:
      Issue: -0.10 | Clean delivery: +0.05
      Flag for review at weight < 0.4
    """
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
        await client.add_episode(
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
        _log_graph_error(f"add_temporal_edge({source_id}->{target_id}): {e}")


def get_active_edges(node_id: str, relationship: str = None) -> list:
    """Returns all edges with weight > 0.1, optionally filtered by relationship type."""
    import asyncio

    async def _search():
        results = await client.search(node_id, num_results=50)
        return results

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                raw = pool.submit(asyncio.run, _search()).result()
        else:
            raw = loop.run_until_complete(_search())

        edges = []
        for edge in raw:
            meta = getattr(edge, "metadata", {}) or {}
            weight = float(meta.get("weight", 1.0))
            if weight <= _INACTIVE_WEIGHT_THRESHOLD:
                continue
            if relationship and meta.get("relationship") != relationship:
                continue
            edges.append(edge)
        return edges
    except Exception as e:
        _log_graph_error(f"get_active_edges({node_id}): {e}")
        return []


def adjust_edge_weight(node_id: str, relationship: str, delta: float) -> None:
    """Adjusts the weight of an existing edge by delta (positive or negative)."""
    edges = get_active_edges(node_id, relationship)
    for edge in edges:
        meta = getattr(edge, "metadata", {}) or {}
        new_weight = max(0.0, min(1.0, float(meta.get("weight", 1.0)) + delta))
        meta["weight"] = new_weight
        source = meta.get("source_id", node_id)
        target = meta.get("target_id", node_id)
        valid_until_str = meta.get("valid_until")
        valid_until = (
            datetime.fromisoformat(valid_until_str) if valid_until_str else None
        )
        add_temporal_edge(source, target, relationship, new_weight, valid_until, meta)


def decay_weights() -> None:
    """
    Runs nightly. Reduces weight on all time-bound edges proportional
    to time elapsed vs valid_until. Logs expired edges to Obsidian.
    """
    import asyncio
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    expired_log = []

    async def _search_all():
        return await client.search("*", num_results=500)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                edges = pool.submit(asyncio.run, _search_all()).result()
        else:
            edges = loop.run_until_complete(_search_all())
    except Exception:
        edges = []

    for edge in edges:
        meta = getattr(edge, "metadata", {}) or {}
        valid_until_str = meta.get("valid_until")
        if not valid_until_str:
            continue
        try:
            valid_until = datetime.fromisoformat(valid_until_str)
        except Exception:
            continue

        created_str = meta.get("created_at", now.isoformat())
        try:
            created_at = datetime.fromisoformat(created_str)
        except Exception:
            created_at = now

        total_seconds = max((valid_until - created_at).total_seconds(), 1)
        elapsed_seconds = (now - created_at).total_seconds()
        decay_fraction = min(elapsed_seconds / total_seconds, 1.0)
        original_weight = float(meta.get("weight", 1.0))
        new_weight = original_weight * (1.0 - decay_fraction)

        source = meta.get("source_id", "")
        target = meta.get("target_id", "")
        relationship = meta.get("relationship", "")

        if new_weight < _INACTIVE_WEIGHT_THRESHOLD:
            expired_log.append(
                f"{now.isoformat()} | EXPIRED | {relationship}: {source} -> {target} "
                f"(weight={new_weight:.3f})"
            )
        else:
            meta["weight"] = new_weight
            add_temporal_edge(source, target, relationship, new_weight, valid_until, meta)

    if expired_log:
        _write_expired_obsidian(expired_log, now.strftime("%Y%m%d"))


def _write_expired_obsidian(entries: list, date_str: str) -> None:
    try:
        _OBSIDIAN_PATH.mkdir(parents=True, exist_ok=True)
        out_file = _OBSIDIAN_PATH / f"expired_edges_{date_str}.md"
        with open(out_file, "a") as f:
            f.write("\n".join(entries) + "\n")
    except Exception:
        pass


def _log_graph_error(msg: str) -> None:
    log_file = Path(__file__).parent.parent / "neural" / "logs" / "graphiti_error.log"
    log_file.parent.mkdir(exist_ok=True)
    with open(log_file, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} | {msg}\n")
