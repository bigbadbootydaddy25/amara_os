"""Lightweight in-memory doubles for the supabase-py client shape used by
app/memory/outcome_log.py and app/memory/retrieval.py, and for the
embedding call in app/llm/provider.py-shaped objects.

No live Supabase or Ollama instance is available in CI/dev sandboxes, so
these fakes exercise the real query-building/filtering code paths (workspace
scoping in particular) without a network dependency.
"""

from __future__ import annotations

import itertools
import uuid
from typing import Any


class FakeResult:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class _InsertOrUpdateQuery:
    def __init__(self, rows: list[dict[str, Any]], op: str, payload: dict[str, Any]) -> None:
        self._rows = rows
        self._op = op
        self._payload = payload
        self._filters: dict[str, Any] = {}

    def eq(self, key: str, value: Any) -> "_InsertOrUpdateQuery":
        self._filters[key] = value
        return self

    def execute(self) -> FakeResult:
        if self._op == "insert":
            row = {**self._payload, "id": str(uuid.uuid4())}
            self._rows.append(row)
            return FakeResult([row])

        if self._op == "update":
            for row in self._rows:
                if all(row.get(k) == v for k, v in self._filters.items()):
                    row.update(self._payload)
                    return FakeResult([row])
            return FakeResult([])

        raise AssertionError(f"unsupported op: {self._op}")


class _RpcQuery:
    def __init__(self, rows: list[dict[str, Any]], params: dict[str, Any]) -> None:
        self._rows = rows
        self._params = params

    def execute(self) -> FakeResult:
        workspace = self._params["match_workspace"]
        task_type = self._params.get("match_task_type")
        count = self._params.get("match_count", 5)

        matches = [
            row
            for row in self._rows
            if row["workspace"] == workspace
            and (task_type is None or row["task_type"] == task_type)
        ]
        return FakeResult(list(itertools.islice(matches, count)))


class FakeSupabaseClient:
    """Mimics `.table(name).insert(...)/.update(...).eq(...).execute()` and
    `.rpc(name, params).execute()` against an in-memory row store, scoped
    per table name -- just enough of the supabase-py surface for
    OutcomeLogStore and similar_outcomes to run against."""

    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.last_rpc: tuple[str, dict[str, Any]] | None = None

    def table(self, name: str) -> "_TableHandle":
        return _TableHandle(self.tables.setdefault(name, []))

    def rpc(self, name: str, params: dict[str, Any]) -> _RpcQuery:
        self.last_rpc = (name, params)
        # match_outcomes reads from outcome_log.
        return _RpcQuery(self.tables.setdefault("outcome_log", []), params)


class _TableHandle:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def insert(self, payload: dict[str, Any]) -> _InsertOrUpdateQuery:
        return _InsertOrUpdateQuery(self._rows, "insert", payload)

    def update(self, payload: dict[str, Any]) -> _InsertOrUpdateQuery:
        return _InsertOrUpdateQuery(self._rows, "update", payload)


class FakeEmbedder:
    async def embed(self, text: str) -> list[float]:
        return [float(len(text))] * 3
