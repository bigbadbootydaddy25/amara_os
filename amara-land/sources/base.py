from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol


@dataclass
class NormalizedRecord:
    """Envelope every source module attaches to each record it fetches.

    `data` holds the source-specific fields. The rest is provenance that every
    later phase (screening, evidence, UI) depends on to judge freshness and trust.
    """

    data: dict[str, Any]
    source: str
    source_url: str
    retrieved_at: datetime
    dataset_published_at: date | None = None


class SourceModule(Protocol):
    """Every module under `sources/` implements this: one `fetch()`, no args, no side effects."""

    def fetch(self) -> list[NormalizedRecord]: ...
