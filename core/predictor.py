from __future__ import annotations

import asyncio
import logging

import schedule

from config import cfg
from core.llm_client import llm

logger = logging.getLogger(__name__)

_IMPROVEMENT_PROMPT = (
    "You are an AI self-improvement advisor for AmaraOS. "
    "Analyze the current routing strategy (Ollama-first, Claude fallback) "
    "and Mem0+Neo4j memory design. Suggest one concrete improvement "
    "to routing logic or memory retrieval that would increase response quality. "
    "Be specific and actionable."
)


class Predictor:
    """Daily self-improvement loop."""

    def start(self) -> None:
        schedule.every().day.at(f"{cfg.improvement_loop_hour:02d}:00").do(
            lambda: asyncio.create_task(self._run_improvement_cycle())
        )
        logger.info("Predictor scheduled at %02d:00 daily", cfg.improvement_loop_hour)

    async def _run_improvement_cycle(self) -> None:
        logger.info("Running daily improvement cycle")
        suggestion = await llm.achat(_IMPROVEMENT_PROMPT)
        logger.info("Improvement suggestion: %s", suggestion)
