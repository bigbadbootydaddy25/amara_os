"""
AMARA OS — ZIP Corridor Tracker
Tracks activity levels and buyer demand by ZIP corridor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from system.vault import (
    list_vault,
    read_vault_file,
    write_vault_file,
    next_id,
    vault_path,
)
from system.config import ACTIVITY_HOT, ACTIVITY_WARM, ACTIVITY_COLD, ACTIVITY_UNKNOWN


@dataclass
class ZipCorridorProfile:
    corridor_id: str
    name: str
    zip_codes: list[str]
    city: str
    state: str
    status: str = ACTIVITY_UNKNOWN
    buyer_count: int = 0
    deal_count: int = 0
    median_arv: float = 0
    min_buyer_price: float = 0
    max_buyer_price: float = 0
    notes: str = ""

    def is_hot(self) -> bool:
        return self.status == ACTIVITY_HOT

    def summary(self) -> str:
        buyer_range = ""
        if self.min_buyer_price and self.max_buyer_price:
            buyer_range = f"${self.min_buyer_price:,.0f} – ${self.max_buyer_price:,.0f}"
        return (
            f"[{self.status.upper()}] {self.corridor_id} — {self.name} | "
            f"ZIPs: {', '.join(self.zip_codes)} | "
            f"Buyers: {self.buyer_count} | "
            f"Deals: {self.deal_count} | "
            f"Buyer Range: {buyer_range or 'TBD'}"
        )


def create_corridor(
    name: str,
    zip_codes: list[str],
    city: str,
    state: str,
    status: str = ACTIVITY_UNKNOWN,
    notes: str = "",
) -> tuple[str, Path]:
    """
    Create a new ZIP corridor file.
    Returns (corridor_id, file_path).
    """
    corridor_id = next_id("ZIP", "zip-corridors")
    today = date.today().isoformat()
    zip_str = ", ".join(zip_codes)
    filename = f"{corridor_id}_{name.replace(' ', '_')}.md"

    template = read_vault_file("zip-corridors", "TEMPLATE.md") or ""
    content = template
    content = content.replace("[CORRIDOR NAME]", name)
    content = content.replace("ZIP-[XXXX]", corridor_id)
    content = content.replace("YYYY-MM-DD", today, 2)
    content = content.replace(
        "- **ZIP Codes:**", f"- **ZIP Codes:** {zip_str}"
    )
    content = content.replace(
        "- **City / Region:**", f"- **City / Region:** {city}, {state}"
    )
    content = content.replace(
        "- **Status:** (hot / warm / cold / unknown)",
        f"- **Status:** {status}",
    )
    if notes:
        content += f"\n\n## Initial Notes\n{notes}\n"

    path = write_vault_file("zip-corridors", filename, content)
    return corridor_id, path


def update_corridor_status(corridor_filename: str, new_status: str, reason: str = "") -> bool:
    """Update the activity status of a corridor."""
    content = read_vault_file("zip-corridors", corridor_filename)
    if content is None:
        return False

    import re
    content = re.sub(
        r"- \*\*Status:\*\*.*",
        f"- **Status:** {new_status}",
        content,
    )
    today = date.today().isoformat()
    content = re.sub(
        r"- \*\*Last Updated:\*\*.*",
        f"- **Last Updated:** {today}",
        content,
    )
    if reason:
        content += f"\n\n> [{today}] Status changed to {new_status}: {reason}\n"

    write_vault_file("zip-corridors", corridor_filename, content)
    return True


def list_hot_corridors() -> list[Path]:
    """Return all corridor files marked as hot."""
    results = []
    for path in list_vault("zip-corridors"):
        content = path.read_text(encoding="utf-8")
        if f"**Status:** {ACTIVITY_HOT}" in content:
            results.append(path)
    return results


def find_corridors_for_zip(zip_code: str) -> list[Path]:
    """Find all corridors that include a given ZIP code."""
    results = []
    for path in list_vault("zip-corridors"):
        content = path.read_text(encoding="utf-8")
        if zip_code in content:
            results.append(path)
    return results
