from __future__ import annotations

from typing import Any

import httpx

from config import cfg


class MiroFish:
    """Miro REST v2 client for knowledge graph visualization."""

    _BASE = "https://api.miro.com/v2"

    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {cfg.miro_access_token}",
            "Content-Type": "application/json",
        }
        self._board_id = cfg.miro_board_id

    def create_sticky(self, text: str, x: float = 0.0, y: float = 0.0) -> dict[str, Any]:
        payload = {
            "data": {"content": text},
            "position": {"x": x, "y": y},
        }
        resp = httpx.post(
            f"{self._BASE}/boards/{self._board_id}/sticky_notes",
            json=payload,
            headers=self._headers,
        )
        resp.raise_for_status()
        return resp.json()

    def create_connector(self, start_id: str, end_id: str) -> dict[str, Any]:
        payload = {
            "startItem": {"id": start_id},
            "endItem": {"id": end_id},
        }
        resp = httpx.post(
            f"{self._BASE}/boards/{self._board_id}/connectors",
            json=payload,
            headers=self._headers,
        )
        resp.raise_for_status()
        return resp.json()

    def map_graph(self, nodes: list[str], edges: list[tuple[str, str]]) -> None:
        node_ids: dict[str, str] = {}
        for i, node in enumerate(nodes):
            x = (i % 5) * 250.0
            y = (i // 5) * 200.0
            sticky = self.create_sticky(node, x=x, y=y)
            node_ids[node] = sticky["id"]

        for src, dst in edges:
            if src in node_ids and dst in node_ids:
                self.create_connector(node_ids[src], node_ids[dst])
