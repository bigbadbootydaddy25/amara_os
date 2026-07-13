"""Client deliverable branding.

Every external deliverable (report, buyer list, export) is signed with
Scott's byline, never an AI system name. `brand_deliverable` is the single
choke point FOREMAN calls before returning client-facing text.
"""

from __future__ import annotations

from app.guards.output_filter import DEFAULT_AI_NAMES, check_ai_names

DEFAULT_BRANDING_LINE = "Prepared by: Scott Schufford | Aces N 8s"


def brand_deliverable(
    text: str,
    *,
    branding_line: str = DEFAULT_BRANDING_LINE,
    ai_names: list[str] | None = None,
) -> str:
    """Append the byline and verify no AI system name survived into the text.

    Raises OutputFilterViolation (via check_ai_names) if one did -- branding
    is not a silent scrub, callers must fix the source text upstream.
    """
    check_ai_names(text, names=ai_names or DEFAULT_AI_NAMES)
    return f"{text.rstrip()}\n\n{branding_line}"
