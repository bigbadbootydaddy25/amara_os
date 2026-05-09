#!/usr/bin/env python3
"""
Entity research module: SOS verification, alias matching, citation building.
All claims require source URLs. No fabricated records.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Entity type detection
# ---------------------------------------------------------------------------

_ENTITY_KEYWORDS: list[tuple[str, str]] = [
    (r"\bllc\b", "LLC"),
    (r"\bl\.l\.c\.", "LLC"),
    (r"\bltd\b", "Ltd"),
    (r"\blp\b", "LP"),
    (r"\blimited partnership\b", "LP"),
    (r"\blimited liability company\b", "LLC"),
    (r"\bcorp\b", "Corp"),
    (r"\bcorporation\b", "Corp"),
    (r"\binc\b", "Inc"),
    (r"\bincorporated\b", "Inc"),
    (r"\bholdings\b", "Holdings"),
    (r"\benterprises\b", "Enterprises"),
    (r"\bproperties\b", "Properties"),
    (r"\brealty\b", "Realty"),
    (r"\binvestments\b", "Investments"),
    (r"\bcapital\b", "Capital"),
    (r"\bgroup\b", "Group"),
    (r"\bpartners\b", "Partners"),
    (r"\btrust\b", "Trust"),
    (r"\bfund\b", "Fund"),
    (r"\bventures\b", "Ventures"),
    (r"\bassociates\b", "Associates"),
    (r"\bmanagement\b", "Management"),
    (r"\bdevelopment\b", "Development"),
    (r"\bservices\b", "Services"),
]


def detect_entity_type(name: str) -> Optional[str]:
    """Return the most specific entity type keyword found, or None."""
    norm = name.lower()
    for pattern, label in _ENTITY_KEYWORDS:
        if re.search(pattern, norm):
            return label
    return None


def is_entity_name(name: str) -> bool:
    return detect_entity_type(name) is not None


# ---------------------------------------------------------------------------
# Name normalisation for alias matching
# ---------------------------------------------------------------------------

_STRIP_LEGAL = re.compile(
    r"\b(llc|l\.l\.c\.|ltd|lp|inc|corp|corporation|incorporated|"
    r"limited|partnership|company|co)\b",
    re.I,
)
_NON_ALNUM = re.compile(r"[^a-z0-9]")


def normalize_entity(name: str) -> str:
    """Alphanum-only, lowercase, legal-suffix stripped."""
    n = name.lower()
    n = _STRIP_LEGAL.sub("", n)
    n = _NON_ALNUM.sub("", n)
    return n


def names_match(a: str, b: str, threshold: int = 0) -> bool:
    """True if normalised forms are identical (exact match after stripping)."""
    return normalize_entity(a) == normalize_entity(b)


def partial_match(query: str, candidates: list[str], min_overlap: float = 0.7) -> list[str]:
    """Return candidates whose normalised form shares ≥ min_overlap of query's characters."""
    nq = normalize_entity(query)
    results = []
    for c in candidates:
        nc = normalize_entity(c)
        if not nc:
            continue
        overlap = len(set(nq) & set(nc)) / max(len(set(nq)), 1)
        if overlap >= min_overlap:
            results.append(c)
    return results


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EntityResearchPacket:
    entity_name: str
    aliases: list[str] = field(default_factory=list)
    entity_type: Optional[str] = None          # LLC, Corp, LP, …
    jurisdiction: str = "Texas"
    sos_status: Optional[str] = None           # Active | Inactive | Forfeited | Unknown
    registered_agent: Optional[str] = None
    registered_office: Optional[str] = None
    franchise_tax_status: Optional[str] = None # Active | Forfeited per TX CPA
    citations: list[str] = field(default_factory=list)   # REQUIRED — source URLs
    confidence: float = 0.0                    # 0.0–1.0
    research_date: str = ""
    flags: list[str] = field(default_factory=list)
    notes: str = ""

    def __post_init__(self):
        if not self.research_date:
            self.research_date = date.today().isoformat()
        if self.entity_type is None:
            self.entity_type = detect_entity_type(self.entity_name)

    def add_flag(self, flag: str) -> None:
        if flag not in self.flags:
            self.flags.append(flag)

    def add_citation(self, url: str) -> None:
        if url and url not in self.citations:
            self.citations.append(url)


# ---------------------------------------------------------------------------
# Research logic (returns structured packets with citations)
# ---------------------------------------------------------------------------

def research_entity(entity_name: str, known_aliases: Optional[list[str]] = None) -> EntityResearchPacket:
    """
    Build a research packet for a single entity name.

    This function sets up the packet structure and determines what to look for.
    Actual lookups must be performed by a human or a downstream agent against
    the URLs listed in each packet's citations field — we do NOT make HTTP
    requests or scrape live data here.
    """
    packet = EntityResearchPacket(entity_name=entity_name)

    if known_aliases:
        packet.aliases = list(known_aliases)

    # --- SOS lookup guidance ------------------------------------------------
    sos_search_url = (
        "https://direct.sos.state.tx.us/acct/corp-search.asp"
        f"?name={entity_name.replace(' ', '+')}&status=A"
    )
    packet.add_citation("https://www.sos.state.tx.us/corp/sosda/index.shtml")
    packet.add_citation(sos_search_url)
    packet.notes += (
        f"SOS verification: search Texas SOS Direct for '{entity_name}'. "
        "Record SOS file number, status, registered agent, and filing date. "
    )

    # --- CPA franchise tax guidance -----------------------------------------
    cpa_url = "https://mycpa.cpa.state.tx.us/coa/"
    packet.add_citation(cpa_url)
    packet.notes += (
        f"Franchise tax: check TX CPA COA for '{entity_name}'. "
        "Record right_to_transact status (Forfeited = entity lost right to do business). "
    )

    # --- Flag setup ---------------------------------------------------------
    if is_entity_name(entity_name):
        packet.confidence = 0.3   # Needs SOS/CPA verification to raise
    else:
        packet.add_flag("not_entity_name")
        packet.confidence = 0.1

    return packet


def cross_reference_aliases(packets: list[EntityResearchPacket]) -> list[EntityResearchPacket]:
    """
    Find packets that are likely aliases of each other (same normalised name)
    and annotate them.
    """
    norm_map: dict[str, list[int]] = {}
    for i, p in enumerate(packets):
        nk = normalize_entity(p.entity_name)
        norm_map.setdefault(nk, []).append(i)

    for indices in norm_map.values():
        if len(indices) < 2:
            continue
        names = [packets[i].entity_name for i in indices]
        for i in indices:
            p = packets[i]
            for name in names:
                if name != p.entity_name and name not in p.aliases:
                    p.aliases.append(name)
            p.add_flag("alias_group")

    return packets


def flag_revoked_entities(packets: list[EntityResearchPacket]) -> list[EntityResearchPacket]:
    """Add entity_revoked flag when sos_status or franchise_tax_status indicate forfeiture."""
    for p in packets:
        if p.sos_status and p.sos_status.lower() in ("inactive", "forfeited", "dissolved"):
            p.add_flag("entity_revoked")
        if p.franchise_tax_status and p.franchise_tax_status.lower() == "forfeited":
            p.add_flag("franchise_tax_forfeited")
    return packets


def build_entity_research_from_names(
    entity_names: list[str],
    alias_map: Optional[dict[str, list[str]]] = None,
) -> list[EntityResearchPacket]:
    """
    Build research packets for a list of entity names.

    alias_map: {canonical_name: [alias1, alias2, ...]}
    """
    packets = []
    seen: set[str] = set()
    for name in entity_names:
        nk = normalize_entity(name)
        if nk in seen:
            continue
        seen.add(nk)
        aliases = (alias_map or {}).get(name, [])
        packets.append(research_entity(name, aliases))

    packets = cross_reference_aliases(packets)
    packets = flag_revoked_entities(packets)
    return packets


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_verified_entities(packets: list[EntityResearchPacket], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = {
        "generated": date.today().isoformat(),
        "total_entities": len(packets),
        "entities": [asdict(p) for p in packets],
    }
    (reports_dir / "VERIFIED_ENTITIES.json").write_text(json.dumps(out, indent=2))


def write_entity_research_packets(packets: list[EntityResearchPacket], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Entity Research Packets",
        "",
        f"**Generated:** {date.today().isoformat()}  ",
        f"**Total Entities:** {len(packets)}",
        "",
    ]
    for p in packets:
        lines.append(f"## {p.entity_name}")
        lines.append(f"- **Type:** {p.entity_type or 'Unknown'}")
        lines.append(f"- **Jurisdiction:** {p.jurisdiction}")
        lines.append(f"- **SOS Status:** {p.sos_status or 'Not verified'}")
        lines.append(f"- **Franchise Tax Status:** {p.franchise_tax_status or 'Not verified'}")
        lines.append(f"- **Registered Agent:** {p.registered_agent or 'Not verified'}")
        lines.append(f"- **Registered Office:** {p.registered_office or 'Not verified'}")
        lines.append(f"- **Confidence:** {p.confidence:.0%}")
        lines.append(f"- **Research Date:** {p.research_date}")
        if p.aliases:
            lines.append(f"- **Aliases:** {', '.join(p.aliases)}")
        if p.flags:
            lines.append(f"- **Flags:** {', '.join(p.flags)}")
        if p.citations:
            lines.append("- **Citations:**")
            for c in p.citations:
                lines.append(f"  - {c}")
        if p.notes:
            lines.append(f"- **Research Notes:** {p.notes}")
        lines.append("")

    (reports_dir / "ENTITY_RESEARCH_PACKETS.md").write_text("\n".join(lines))
