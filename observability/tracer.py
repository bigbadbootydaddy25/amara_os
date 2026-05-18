from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from config import cfg

logger = logging.getLogger(__name__)


class _NoopTrace:
    def span(self, name: str) -> "_NoopTrace":
        return self

    def end(self) -> None:
        pass


@contextmanager
def _noop_ctx(_name: str) -> Generator[None, None, None]:
    yield


class Tracer:
    def __init__(self) -> None:
        self._lf = None
        self._current_trace = None
        if cfg.langfuse_public_key and cfg.langfuse_secret_key:
            try:
                from langfuse import Langfuse
                self._lf = Langfuse(
                    public_key=cfg.langfuse_public_key,
                    secret_key=cfg.langfuse_secret_key,
                    host=cfg.langfuse_host,
                )
            except Exception as exc:
                logger.warning("Langfuse init failed: %s", exc)

    @contextmanager
    def trace(self, name: str, session_id: str = "default") -> Generator[None, None, None]:
        if self._lf is None:
            yield
            return
        t = self._lf.trace(name=name, session_id=session_id)
        self._current_trace = t
        try:
            yield
        finally:
            self._current_trace = None

    @contextmanager
    def span(self, name: str) -> Generator[None, None, None]:
        if self._lf is None or self._current_trace is None:
            yield
            return
        s = self._current_trace.span(name=name)
        try:
            yield
        finally:
            s.end()
