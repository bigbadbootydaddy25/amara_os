"""Output guard rails: the last thing any FOREMAN result passes through
before it reaches Scott or a client deliverable.

Hard rules encoded here (see AGENTS.md / build brief):
  - HomeVestors can never appear in outbound content, anywhere.
  - Client deliverables never name an AI system/agent (AMARA, FOREMAN, ...).
  - No ARV-percentage formula pattern (e.g. "70% of ARV") -- the SFR
    formula is locked to Buyer's Max Offer - Repairs - Assignment Fee.
"""

from __future__ import annotations

import re

DEFAULT_BLACKLIST_TERMS = ["HomeVestors"]
DEFAULT_AI_NAMES = ["AMARA", "FOREMAN", "Nova", "Ollama", "Claude", "Anthropic"]

# Matches phrases like "70% of ARV", "75%ARV", "70 percent of ARV".
ARV_PERCENTAGE_PATTERN = re.compile(
    r"\b\d{1,3}\s*(%|percent)\s*(of\s+)?ARV\b", re.IGNORECASE
)


class OutputFilterViolation(ValueError):
    def __init__(self, reason: str, *, matched: str | None = None) -> None:
        self.reason = reason
        self.matched = matched
        super().__init__(reason)


def check_blacklist(text: str, *, terms: list[str] | None = None) -> None:
    for term in terms or DEFAULT_BLACKLIST_TERMS:
        if term.lower() in text.lower():
            raise OutputFilterViolation(f'blacklisted term "{term}" found in output', matched=term)


def check_formula(text: str) -> None:
    match = ARV_PERCENTAGE_PATTERN.search(text)
    if match:
        raise OutputFilterViolation(
            "ARV-percentage formula pattern is not permitted; the locked SFR formula is "
            "Buyer's Max Offer - Repairs - Assignment Fee = Net to Seller",
            matched=match.group(0),
        )


def check_ai_names(text: str, *, names: list[str] | None = None) -> None:
    for name in names or DEFAULT_AI_NAMES:
        if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
            raise OutputFilterViolation(
                f'AI system/agent name "{name}" is not permitted in a client deliverable',
                matched=name,
            )


def run_output_filter(
    text: str,
    *,
    client_deliverable: bool = False,
    blacklist_terms: list[str] | None = None,
    ai_names: list[str] | None = None,
) -> None:
    """Raise OutputFilterViolation on any hard-rule breach. Callers (FOREMAN)
    turn this into an HTTP 422 and log the violation."""
    check_blacklist(text, terms=blacklist_terms)
    check_formula(text)
    if client_deliverable:
        check_ai_names(text, names=ai_names)
