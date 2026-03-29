"""
AMARA OS — Vault I/O
Read and write system memory (markdown files) from the vault.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path


VAULT_ROOT = Path(__file__).parent.parent


def vault_path(folder: str, filename: str) -> Path:
    """Return absolute path for a vault file."""
    return VAULT_ROOT / folder / filename


def ensure_vault_dirs() -> None:
    """Create all vault directories if they don't exist."""
    dirs = [
        "buyers", "deals", "land", "markets",
        "zip-corridors", "playbooks", "observations",
        "deal-results", "system",
    ]
    for d in dirs:
        (VAULT_ROOT / d).mkdir(exist_ok=True)


def list_vault(folder: str) -> list[Path]:
    """List all markdown files in a vault folder."""
    p = VAULT_ROOT / folder
    if not p.exists():
        return []
    return sorted(p.glob("*.md"))


def read_vault_file(folder: str, filename: str) -> str | None:
    """Read a vault markdown file. Returns None if not found."""
    path = vault_path(folder, filename)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def write_vault_file(folder: str, filename: str, content: str) -> Path:
    """Write content to a vault markdown file. Creates folder if needed."""
    path = vault_path(folder, filename)
    path.parent.mkdir(exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def next_id(prefix: str, folder: str) -> str:
    """
    Generate the next sequential ID for a vault folder.
    E.g., BUY-0001, DEAL-0002, LAND-0003
    """
    existing = list_vault(folder)
    pattern = re.compile(rf"{re.escape(prefix)}-(\d+)", re.IGNORECASE)
    max_num = 0
    for f in existing:
        m = pattern.search(f.stem)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"{prefix}-{max_num + 1:04d}"


def search_vault(folder: str, keyword: str) -> list[tuple[Path, list[str]]]:
    """
    Full-text search across vault files in a folder.
    Returns list of (path, matching_lines).
    """
    results = []
    for path in list_vault(folder):
        text = path.read_text(encoding="utf-8")
        matches = [
            line.strip()
            for line in text.splitlines()
            if keyword.lower() in line.lower()
        ]
        if matches:
            results.append((path, matches))
    return results


def find_buyer_file(buyer_id: str) -> Path | None:
    """Find a buyer file by ID."""
    for path in list_vault("buyers"):
        if buyer_id.upper() in path.name.upper():
            return path
    return None


def find_deal_file(deal_id: str) -> Path | None:
    """Find a deal file by ID in deals/ or land/ folders."""
    for folder in ("deals", "land"):
        for path in list_vault(folder):
            if deal_id.upper() in path.name.upper():
                return path
    return None


def create_buyer_file(
    name: str,
    company: str = "",
    phone: str = "",
    email: str = "",
    source: str = "",
    notes: str = "",
) -> tuple[str, Path]:
    """
    Create a new buyer profile file from the template.
    Returns (buyer_id, file_path).
    """
    buyer_id = next_id("BUY", "buyers")
    today = date.today().isoformat()
    filename = f"{buyer_id}_{name.replace(' ', '_')}.md"

    template = read_vault_file("buyers", "TEMPLATE.md") or ""

    content = template
    content = content.replace("[BUYER NAME]", name)
    content = content.replace("BUY-[XXXX]", buyer_id)
    content = content.replace("YYYY-MM-DD", today, 2)  # Added + Last Contact
    if company:
        content = content.replace("- **Company:**", f"- **Company:** {company}")
    if phone:
        content = content.replace("- **Phone:**", f"- **Phone:** {phone}")
    if email:
        content = content.replace("- **Email:**", f"- **Email:** {email}")
    if source:
        content = content.replace(
            "- **Source:** (referral / cold outreach / network / etc.)",
            f"- **Source:** {source}",
        )
    if notes:
        content += f"\n\n## Additional Notes\n{notes}\n"

    path = write_vault_file("buyers", filename, content)
    return buyer_id, path


def append_observation(
    observation_text: str,
    obs_type: str = "general",
    related_deal: str = "",
    related_buyer: str = "",
    related_market: str = "",
) -> tuple[str, Path]:
    """
    Create a new observation file.
    Returns (obs_id, file_path).
    """
    obs_id = next_id("OBS", "observations")
    today = date.today().isoformat()
    filename = f"{obs_id}_{today}.md"

    template = read_vault_file("observations", "TEMPLATE.md") or ""
    content = template
    content = content.replace("OBS-[XXXX]", obs_id)
    content = content.replace("YYYY-MM-DD", today)
    content = content.replace("[TITLE]", observation_text[:60])
    content = content.replace(
        "(market / buyer / pricing / deal / corridor / general)", obs_type
    )
    if related_deal:
        content = content.replace("(if applicable)", related_deal, 1)
    if related_buyer:
        content = content.replace("(if applicable)", related_buyer, 1)
    if related_market:
        content = content.replace("(if applicable)", related_market, 1)
    content += f"\n\n## Full Observation\n{observation_text}\n"

    path = write_vault_file("observations", filename, content)
    return obs_id, path


def record_deal_result(
    deal_id: str,
    contract_price: float,
    buyer_price: float,
    assignment_fee: float,
    buyer_feedback: str = "",
    lessons: str = "",
) -> tuple[str, Path]:
    """
    Record a closed deal result.
    Returns (result_id, file_path).
    """
    result_id = next_id("RESULT", "deal-results")
    today = date.today().isoformat()
    filename = f"{result_id}_{deal_id}_{today}.md"

    template = read_vault_file("deal-results", "TEMPLATE.md") or ""
    content = template
    content = content.replace("RESULT-[XXXX]", result_id)
    content = content.replace("(link to deals/ or land/)", deal_id)
    content = content.replace("[DEAL ID]", deal_id)
    content = content.replace(
        "- **Contract Price (from seller):** $",
        f"- **Contract Price (from seller):** ${contract_price:,.0f}",
    )
    content = content.replace(
        "- **Buyer Purchase Price:** $",
        f"- **Buyer Purchase Price:** ${buyer_price:,.0f}",
    )
    content = content.replace(
        "- **Assignment Fee Collected:** $",
        f"- **Assignment Fee Collected:** ${assignment_fee:,.0f}",
    )

    if buyer_feedback:
        content += f"\n\n## Buyer Feedback Notes\n{buyer_feedback}\n"
    if lessons:
        content += f"\n\n## Lessons\n{lessons}\n"

    path = write_vault_file("deal-results", filename, content)
    return result_id, path
