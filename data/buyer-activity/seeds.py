"""
Load buyer entity seeds from buyers/*.md files.

Seeds provide known buyer identities (name, entity, ID) for enrichment.
A seed match is purely additive — profiles are built regardless of whether a
match is found, satisfying requirement 4.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Default location: repo-root/buyers/ — two levels above this file
_REPO_ROOT = Path(__file__).parent.parent.parent
BUYERS_DIR = _REPO_ROOT / "buyers"


@dataclass
class BuyerSeed:
    buyer_id: str
    buyer_name: str
    entity_name: Optional[str] = None
    status: str = "unknown"
    zip_codes: list[str] = field(default_factory=list)


def load_seeds(buyers_dir: Path = BUYERS_DIR) -> list[BuyerSeed]:
    """Return all BuyerSeed objects parsed from buyers/BUY-*.md files."""
    if not buyers_dir.exists():
        return []
    seeds = []
    for md in sorted(buyers_dir.glob("BUY-*.md")):
        seed = _parse_md(md)
        if seed:
            seeds.append(seed)
    return seeds


def match_seed(
    buyer_entity: Optional[str],
    buyer_name: Optional[str],
    seeds: list[BuyerSeed],
) -> Optional[BuyerSeed]:
    """
    Fuzzy-match a transaction buyer to a known seed.

    Normalises both sides to lowercase alphanumeric only before comparing.
    Returns the first matching seed, or None if no match.
    """
    candidates = [c for c in (buyer_entity, buyer_name) if c]
    for candidate in candidates:
        norm = _norm(candidate)
        for seed in seeds:
            if seed.entity_name and _norm(seed.entity_name) == norm:
                return seed
            if _norm(seed.buyer_name) == norm:
                return seed
    return None


# ── Markdown parser ───────────────────────────────────────────────────────────

def _parse_md(path: Path) -> Optional[BuyerSeed]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    # H1 → buyer name
    name_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    buyer_name = name_m.group(1).strip() if name_m else path.stem

    # ## Entity → entity name
    entity_m = re.search(r"##\s+Entity\s*\n+([^\n]+)", text)
    entity_name = entity_m.group(1).strip() if entity_m else None
    if entity_name and entity_name.lower() in ("llc or individual", "n/a", ""):
        entity_name = None

    # **ID:** BUY-XXXX
    id_m = re.search(r"\*\*ID:\*\*\s*(BUY-\d+)", text)
    buyer_id = id_m.group(1) if id_m else path.stem

    # **Status:** active|inactive|…
    status_m = re.search(r"\*\*Status:\*\*\s*(\w+)", text)
    status = status_m.group(1).lower() if status_m else "unknown"

    # ZIP codes listed under ## ZIP Codes
    zip_m = re.search(r"##\s+ZIP Codes\s*\n([\s\S]+?)(?=\n##|\Z)", text)
    zip_codes: list[str] = []
    if zip_m:
        zip_codes = re.findall(r"\b(\d{5})\b", zip_m.group(1))

    return BuyerSeed(
        buyer_id=buyer_id,
        buyer_name=buyer_name,
        entity_name=entity_name,
        status=status,
        zip_codes=zip_codes,
    )


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())
