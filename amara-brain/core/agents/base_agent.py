"""
Base class for all AMARA agents.
All inference goes through OpenClaw — never Ollama or Anthropic directly.
"""

from neural.openclaw_router import route


class BaseAgent:
    task_type: str = "pain_point_analysis"
    SYSTEM_PROMPT: str = "You are an AMARA intelligence agent. Output JSON only."

    def run(self, prompt: str) -> dict:
        """Routes inference through OpenClaw and returns parsed dict."""
        result = route(
            task_type=self.task_type,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return result
