from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from langfuse import Langfuse

from config import cfg


class Tracer:
    def __init__(self) -> None:
        self._lf = Langfuse(
            public_key=cfg.langfuse_public_key,
            secret_key=cfg.langfuse_secret_key,
            host=cfg.langfuse_host,
        )
        self._current_trace = None

    @contextmanager
    def trace(self, name: str, session_id: str = "default") -> Generator[None, None, None]:
        t = self._lf.trace(name=name, session_id=session_id)
        self._current_trace = t
        try:
            yield
        finally:
            self._current_trace = None

    @contextmanager
    def span(self, name: str) -> Generator[None, None, None]:
        if self._current_trace:
            span = self._current_trace.span(name=name)
            try:
                yield
            finally:
                span.end()
        else:
            yield
