from __future__ import annotations

import asyncio
import logging

import schedule

from anthropic import AsyncAnthropic
from config import cfg

logger = logging.getLogger(__name__)


class Predictor:
    """Daily self-improvement loop that asks Claude to suggest routing/memory improvements."""

    def __init__(self) -> None:
        self._claude = AsyncAnthropic(api_key=cfg.claude_api_key)

    def start(self) -> None:
        schedule.every().day.at(f"{cfg.improvement_loop_hour:02d}:00").do(
            lambda: asyncio.create_task(self._run_improvement_cycle())
        )
        logger.info("Predictor scheduled at %02d:00 daily", cfg.improvement_loop_hour)

    async def _run_improvement_cycle(self) -> None:
        logger.info("Running daily improvement cycle")
        suggestion = await self._ask_claude()
        logger.info("Improvement suggestion: %s", suggestion)

    async def _ask_claude(self) -> str:
        prompt = (
            "You are an AI self-improvement advisor for AmaraOS. "
            "Analyze the current routing strategy (Ollama-first, Claude fallback) "
            "and Mem0+Neo4j memory design. Suggest one concrete improvement "
            "to routing logic or memory retrieval that would increase response quality. "
            "Be specific and actionable."
        )
        msg = await self._claude.messages.create(
            model=cfg.claude_model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
