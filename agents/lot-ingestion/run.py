"""
AI_BRAIN Lot Ingestion Pipeline
Parses raw infill lot lead CSVs, detects builder/infill signals,
geo-clusters nearby addresses, cross-references buyers, and generates
INFILL_CLUSTERS.json, BUILDER_CORRIDORS.json, LOT_ASSEMBLAGE_OPPORTUNITIES.md.

Source: data/deal-leads/raw/*.csv
Output: data/deal-leads/{INFILL_CLUSTERS,BUILDER_CORRIDORS}.json
        data/deal-leads/LOT_ASSEMBLAGE_OPPORTUNITIES.md
        agents/lot-ingestion/reports/<timestamp>/
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR        = ROOT / "data" / "deal-leads" / "raw"
OUT_DIR        = ROOT / "data" / "deal-leads"
REPORTS_DIR    = ROOT / "agents" / "lot-ingestion" / "reports"
DEAL_DATA_DIR  = ROOT / "data" / "deal-scoring"

# ── Signal definitions ────────────────────────────────────────────────────────

SIGNAL_PATTERNS: dict[str, list[str]] = {
    "cleared_lot":          ["cleared lot", "cleared land", "cleared,", " cleared ", "bare lot", "builder-ready", "builder ready"],
    "utilities_available":  ["utilities available", "utilities on site", "utilities at street", "all utilities", "water available", "electric available", "utility"],
    "adjacent_lots":        ["adjacent lot", "adjacent to", "adjacent parcel", "next door", "neighboring lot", "adjacent lots", "same block"],
    "corner_lot":           ["corner lot", "corner of", "corner parcel", "corner property"],
    "fenced":               ["fenced", "privacy fence", "chain link", "fence"],
    "probate":              ["probate", "estate sale", "estate seller", "heir property", "heirship", "estate/probate"],
    "bishop_arts":          ["bishop arts", "bishop arts district", "bishop arts corridor"],
    "trinity_groves":       ["trinity groves"],
}

# Strategy boost definitions
STRATEGY_BOOSTS: dict[str, dict] = {
    "infill_build": {
        "requires_any": ["cleared_lot", "utilities_available"],
        "boost": 15,
        "description": "Cleared + utilities → immediate infill build candidate",
    },
    "builder_assignment": {
        "requires_any": ["bishop_arts", "trinity_groves", "adjacent_lots"],
        "boost": 20,
        "description": "High-demand corridor → builder assignment opportunity",
    },
    "land_flip": {
        "requires_any": ["probate"],
        "boost": 10,
        "description": "Distressed/probate origin → land flip opportunity",
    },
    "corner_premium": {
        "requires_any": ["corner_lot"],
        "boost": 5,
        "description": "Corner lot → premium resale / development potential",
    },
    "assemblage_candidate": {
        "requires_any": ["adjacent_lots"],
        "boost": 8,
        "description": "Adjacent lots noted → assemblage opportunity",
    },
}

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class Broker:
    name: str
    phone: str
    email: str
    raw: str

@dataclass
class LotLead:
    lot_id: str
    raw_address: str
    street_number: int
    street_name: str       # normalised lower
    street_full: str       # original casing
    city: str
    state: str
    zip_code: str
    price_raw: str
    price_usd: int | None
    size_acres: float | None
    details: str
    signals: list[str]
    strategies: list[str]
    strategy_boost: int
    broker: Broker
    source_file: str
    source_row: int
    base_score: int

@dataclass
class LotCluster:
    cluster_id: str
    street_name: str
    street_full: str
    block_range: tuple[int, int]    # (lo_block, hi_block) in hundreds
    lot_ids: list[str]
    lot_count: int
    total_acres: float
    price_range: tuple[int, int]
    all_signals: list[str]          # union of all lot signals
    all_strategies: list[str]
    cluster_score: int              # base + boosts
    assemblage_potential: str       # "high" | "medium" | "low"
    brokers: list[str]              # unique broker names in cluster
    buyer_matches: list[str]        # matched buyer names
    evidence: list[dict]            # per-lot evidence rows

@dataclass
class BuilderCorridor:
    corridor_id: str
    street_name: str
    street_full: str
    cluster_ids: list[str]
    total_lots: int
    total_acres: float
    confidence: str                 # "high" | "medium" | "low"
    confidence_score: int
    dominant_broker: str
    broker_dispo_confidence: str    # "high" | "medium" | "low"
    signals: list[str]
    strategies: list[str]
    district: str                   # "Bishop Arts" | "Trinity Groves" | "Other"
    assemblage_potential: str
    price_range: tuple[int, int]
    evidence_files: list[str]

# ── Parsers ───────────────────────────────────────────────────────────────────

_PRICE_RE  = re.compile(r"\$?([\d,]+)")
_PHONE_RE  = re.compile(r"(\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4})")
_EMAIL_RE  = re.compile(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")
_ADDR_RE   = re.compile(
    r"^(\d+)\s+(.+?),?\s+(Dallas|Irving|Grand Prairie|Garland|Mesquite|Duncanville|DeSoto|Cedar Hill|Lancaster|Balch Springs|Seagoville|Hutchins|Wilmer|Ferris),?\s*(TX)?,?\s*(\d{5})?",
    re.IGNORECASE,
)


def _parse_price(raw: str) -> int | None:
    m = _PRICE_RE.search(raw.replace(",", ""))
    return int(m.group(1).replace(",", "")) if m else None


def _parse_size(raw: str) -> float | None:
    raw = str(raw).strip()
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_broker(raw: str) -> Broker:
    phones = _PHONE_RE.findall(raw)
    emails = _EMAIL_RE.findall(raw)
    # Name is everything before the first | or phone
    name_part = re.split(r"\||\(?\d{3}\)?", raw)[0].strip().rstrip(",").strip()
    # Strip "Broker", "Realtor", "Agent" suffix for clean name
    name_clean = re.sub(r",?\s*(Broker|Realtor|Agent|Realtor Associate)\s*$", "", name_part, flags=re.I).strip()
    return Broker(
        name=name_clean or name_part,
        phone=phones[0] if phones else "",
        email=emails[0] if emails else "",
        raw=raw.strip(),
    )


def _normalise_street(raw_street: str) -> str:
    s = raw_street.lower().strip()
    s = re.sub(r"\bst\b\.?$", "st", s)
    s = re.sub(r"\bave\b\.?$", "ave", s)
    s = re.sub(r"\bblvd\b\.?$", "blvd", s)
    s = re.sub(r"\bdr\b\.?$", "dr", s)
    s = re.sub(r"\brd\b\.?$", "rd", s)
    s = re.sub(r"\bln\b\.?$", "ln", s)
    s = re.sub(r"\bway\b\.?$", "way", s)
    return s.strip()


def _parse_address(raw: str) -> tuple[int, str, str, str, str, str]:
    """Return (street_number, street_name_normalised, street_full, city, state, zip)."""
    m = _ADDR_RE.match(raw.strip())
    if m:
        num     = int(m.group(1))
        street  = m.group(2).strip()
        city    = m.group(3).strip()
        state   = (m.group(4) or "TX").strip()
        zipcode = (m.group(5) or "").strip()
        return num, _normalise_street(street), street, city, state, zipcode

    # Fallback: split on first comma
    parts = raw.split(",")
    head  = parts[0].strip()
    num_m = re.match(r"^(\d+)\s+(.*)", head)
    if num_m:
        num    = int(num_m.group(1))
        street = num_m.group(2).strip()
        city   = parts[1].strip() if len(parts) > 1 else ""
        return num, _normalise_street(street), street, city, "TX", ""
    return 0, "", raw.strip(), "", "TX", ""


def _detect_signals(details: str) -> list[str]:
    lower = details.lower()
    found: list[str] = []
    for sig, patterns in SIGNAL_PATTERNS.items():
        if any(p in lower for p in patterns):
            found.append(sig)
    return found


def _apply_strategies(signals: list[str]) -> tuple[list[str], int]:
    active: list[str] = []
    total_boost = 0
    for name, defn in STRATEGY_BOOSTS.items():
        if any(s in signals for s in defn["requires_any"]):
            active.append(name)
            total_boost += defn["boost"]
    return active, total_boost


# ── CSV ingestion ─────────────────────────────────────────────────────────────

def ingest_csv(path: Path) -> list[LotLead]:
    lots: list[LotLead] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row_num, row in enumerate(reader, start=2):
            raw_addr = row.get("Address", "").strip()
            if not raw_addr:
                continue

            num, street_norm, street_full, city, state, zipcode = _parse_address(raw_addr)
            price_raw = row.get("Price", "").strip()
            size_raw  = row.get("Size (Acres)", "").strip()
            details   = row.get("Details", "").strip()
            contact   = row.get("Contact Information", "").strip()

            signals, strategies = _detect_signals(details), []
            strategies, boost   = _apply_strategies(signals)
            broker              = _parse_broker(contact)
            lot_id              = f"LOT-{path.stem.upper()[:8]}-{row_num:04d}"

            lots.append(LotLead(
                lot_id=lot_id,
                raw_address=raw_addr,
                street_number=num,
                street_name=street_norm,
                street_full=street_full,
                city=city,
                state=state,
                zip_code=zipcode,
                price_raw=price_raw,
                price_usd=_parse_price(price_raw),
                size_acres=_parse_size(size_raw),
                details=details,
                signals=signals,
                strategies=strategies,
                strategy_boost=boost,
                broker=broker,
                source_file=path.name,
                source_row=row_num,
                base_score=50,
            ))
    return lots


def ingest_all(raw_dir: Path = RAW_DIR) -> list[LotLead]:
    all_lots: list[LotLead] = []
    for csv_path in sorted(raw_dir.glob("*.csv")):
        print(f"  ingesting {csv_path.name} ...", end=" ", flush=True)
        lots = ingest_csv(csv_path)
        print(f"{len(lots)} lots")
        all_lots.extend(lots)
    return all_lots


# ── Geo-clustering ────────────────────────────────────────────────────────────
# Cluster key: (normalised_street_name, hundreds_block)
# Lots within BLOCK_RADIUS blocks of the nearest same-street lot merge.

BLOCK_RADIUS = 2   # lots within 2 blocks (200 address units) cluster together


def _block(street_number: int) -> int:
    return (street_number // 100) * 100


def geo_cluster(lots: list[LotLead]) -> list[LotCluster]:
    # Group by street name
    by_street: dict[str, list[LotLead]] = defaultdict(list)
    for lot in lots:
        by_street[lot.street_name].append(lot)

    clusters: list[LotCluster] = []
    cluster_counter = 0

    for street_norm, street_lots in by_street.items():
        street_lots_sorted = sorted(street_lots, key=lambda l: l.street_number)

        # Greedy merge: start a new cluster when gap > BLOCK_RADIUS blocks
        current_group: list[LotLead] = []
        for lot in street_lots_sorted:
            if not current_group:
                current_group.append(lot)
            else:
                gap = abs(_block(lot.street_number) - _block(current_group[-1].street_number))
                if gap <= BLOCK_RADIUS * 100:
                    current_group.append(lot)
                else:
                    clusters.append(_make_cluster(current_group, cluster_counter))
                    cluster_counter += 1
                    current_group = [lot]
        if current_group:
            clusters.append(_make_cluster(current_group, cluster_counter))
            cluster_counter += 1

    return clusters


def _assemblage_potential(lot_count: int, block_span: int) -> str:
    if lot_count >= 4 and block_span <= 1:
        return "high"
    if lot_count >= 3 or (lot_count >= 2 and block_span == 0):
        return "medium"
    return "low"


def _make_cluster(lots: list[LotLead], idx: int) -> LotCluster:
    street_full  = lots[0].street_full
    street_norm  = lots[0].street_name
    blocks       = [_block(l.street_number) for l in lots]
    lo_block, hi_block = min(blocks), max(blocks)
    block_span   = (hi_block - lo_block) // 100

    all_signals  = sorted(set(s for l in lots for s in l.signals))
    all_strats   = sorted(set(s for l in lots for s in l.strategies))
    prices       = [l.price_usd for l in lots if l.price_usd]
    acres        = sum(l.size_acres for l in lots if l.size_acres)
    brokers      = sorted(set(l.broker.name for l in lots if l.broker.name))
    base_score   = 50
    boost        = max((l.strategy_boost for l in lots), default=0)
    # Additional cluster-level boost for assemblage
    if len(lots) >= 4:
        boost += 15
    elif len(lots) >= 3:
        boost += 8
    elif len(lots) >= 2:
        boost += 4

    return LotCluster(
        cluster_id=f"CLU-{street_norm.replace(' ', '-').upper()[:16]}-{idx:03d}",
        street_name=street_norm,
        street_full=street_full,
        block_range=(lo_block, hi_block),
        lot_ids=[l.lot_id for l in lots],
        lot_count=len(lots),
        total_acres=round(acres, 3),
        price_range=(min(prices) if prices else 0, max(prices) if prices else 0),
        all_signals=all_signals,
        all_strategies=all_strats,
        cluster_score=min(100, base_score + boost),
        assemblage_potential=_assemblage_potential(len(lots), block_span),
        brokers=brokers,
        buyer_matches=[],   # filled later
        evidence=[
            {
                "lot_id":    l.lot_id,
                "address":   l.raw_address,
                "price":     l.price_raw,
                "size":      l.size_acres,
                "signals":   l.signals,
                "strategies": l.strategies,
                "broker":    l.broker.name,
                "phone":     l.broker.phone,
                "email":     l.broker.email,
                "source":    f"{l.source_file}:row{l.source_row}",
                "details":   l.details[:200],
            }
            for l in lots
        ],
    )


# ── Buyer cross-reference ─────────────────────────────────────────────────────

def _load_json_list(path: Path, key: str | None = None) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as fh:
        data = json.load(fh)
    if key and isinstance(data, dict):
        return data.get(key, [])
    if isinstance(data, list):
        return data
    return []


def _buyer_name_set(buyers: list[dict]) -> set[str]:
    names: set[str] = set()
    for b in buyers:
        for field_name in ("name", "buyer_name", "entity", "entity_name"):
            val = b.get(field_name, "")
            if val:
                names.add(str(val).strip().lower())
    return names


def cross_reference_buyers(
    clusters: list[LotCluster],
    lots: list[LotLead],
) -> list[LotCluster]:
    hot_buyers     = _load_json_list(DEAL_DATA_DIR / "HOT_BUYERS.json")
    active_buyers  = _load_json_list(DEAL_DATA_DIR / "ACTIVE_BUYERS.json")
    builder_matches= _load_json_list(DEAL_DATA_DIR / "BUILDER_MATCHES.json")

    all_buyers = {**{b.get("name", b.get("buyer_name", "")).strip(): b for b in hot_buyers},
                  **{b.get("name", b.get("buyer_name", "")).strip(): b for b in active_buyers},
                  **{b.get("name", b.get("buyer_name", "")).strip(): b for b in builder_matches}}

    buyer_names_lower = {k.lower(): k for k in all_buyers if k}

    lot_by_id = {l.lot_id: l for l in lots}

    for cluster in clusters:
        matched: list[str] = []
        for lot_id in cluster.lot_ids:
            lot = lot_by_id.get(lot_id)
            if not lot:
                continue
            # Signal-based buyer matching: builder_assignment lots → check builder matches
            if "builder_assignment" in lot.strategies or "bishop_arts" in lot.signals or "trinity_groves" in lot.signals:
                matched.extend(buyer_names_lower.values())
                break

        cluster.buyer_matches = list(dict.fromkeys(matched))[:10]

    return clusters


# ── Broker frequency + dispo confidence ───────────────────────────────────────

def broker_dispo_confidence(broker_name: str, all_lots: list[LotLead]) -> tuple[int, str]:
    count = sum(1 for l in all_lots if l.broker.name == broker_name)
    if count >= 4:
        return count, "high"
    if count >= 2:
        return count, "medium"
    return count, "low"


# ── Corridor detection ────────────────────────────────────────────────────────
# A corridor is a street with 3+ clustered lots, treated as a builder opportunity zone.

CORRIDOR_MIN_LOTS = 3


def detect_corridors(
    clusters: list[LotCluster],
    all_lots: list[LotLead],
) -> list[BuilderCorridor]:
    # Group clusters by street
    by_street: dict[str, list[LotCluster]] = defaultdict(list)
    for c in clusters:
        by_street[c.street_name].append(c)

    corridors: list[BuilderCorridor] = []
    corr_idx = 0

    for street_norm, street_clusters in by_street.items():
        total_lots  = sum(c.lot_count for c in street_clusters)
        if total_lots < CORRIDOR_MIN_LOTS:
            continue

        total_acres = round(sum(c.total_acres for c in street_clusters), 3)
        all_signals = sorted(set(s for c in street_clusters for s in c.all_signals))
        all_strats  = sorted(set(s for c in street_clusters for s in c.all_strategies))

        prices = [p for c in street_clusters for p in c.price_range if p > 0]

        # Detect district
        if "bishop_arts" in all_signals:
            district = "Bishop Arts"
        elif "trinity_groves" in all_signals:
            district = "Trinity Groves"
        else:
            district = "Other"

        # Dominant broker by lot count
        broker_counts: dict[str, int] = defaultdict(int)
        lot_by_id = {l.lot_id: l for l in all_lots}
        for c in street_clusters:
            for lid in c.lot_ids:
                lot = lot_by_id.get(lid)
                if lot:
                    broker_counts[lot.broker.name] += 1
        dominant_broker = max(broker_counts, key=lambda k: broker_counts[k]) if broker_counts else ""
        broker_count, broker_dispo = broker_dispo_confidence(dominant_broker, all_lots)

        # Confidence score
        confidence_score = total_lots * 10
        if "bishop_arts" in all_signals or "trinity_groves" in all_signals:
            confidence_score += 20
        if "cleared_lot" in all_signals:
            confidence_score += 10
        if "utilities_available" in all_signals:
            confidence_score += 10
        if "adjacent_lots" in all_signals:
            confidence_score += 10
        if broker_dispo == "high":
            confidence_score += 15
        elif broker_dispo == "medium":
            confidence_score += 8

        # Overall assemblage
        best_assemblage = max(
            (c.assemblage_potential for c in street_clusters),
            key=lambda x: {"high": 2, "medium": 1, "low": 0}[x],
            default="low",
        )

        confidence = "high" if confidence_score >= 80 else ("medium" if confidence_score >= 50 else "low")
        street_full = street_clusters[0].street_full

        corridors.append(BuilderCorridor(
            corridor_id=f"CORR-{street_norm.replace(' ', '-').upper()[:16]}-{corr_idx:03d}",
            street_name=street_norm,
            street_full=street_full,
            cluster_ids=[c.cluster_id for c in street_clusters],
            total_lots=total_lots,
            total_acres=total_acres,
            confidence=confidence,
            confidence_score=min(100, confidence_score),
            dominant_broker=dominant_broker,
            broker_dispo_confidence=broker_dispo,
            signals=all_signals,
            strategies=all_strats,
            district=district,
            assemblage_potential=best_assemblage,
            price_range=(min(prices) if prices else 0, max(prices) if prices else 0),
            evidence_files=sorted(set(
                lot_by_id[lid].source_file
                for c in street_clusters
                for lid in c.lot_ids
                if lid in lot_by_id
            )),
        ))
        corr_idx += 1

    return sorted(corridors, key=lambda c: -c.confidence_score)


# ── Feed downstream agents ────────────────────────────────────────────────────

def feed_deal_scoring(clusters: list[LotCluster], lots: list[LotLead]) -> list[dict]:
    """Emit deal-scoring-engine compatible deal dicts for clustered lots."""
    lot_by_id = {l.lot_id: l for l in lots}
    deal_records: list[dict] = []

    for cluster in clusters:
        for lot_id in cluster.lot_ids:
            lot = lot_by_id.get(lot_id)
            if not lot:
                continue
            deal_records.append({
                "deal_id":    lot.lot_id,
                "deal_side":  "land",
                "owner_name": None,     # populated by entity-resolution downstream
                "buyer_name": None,
                "builder_name": None,
                "base_score": min(100, lot.base_score + lot.strategy_boost),
                "address":    lot.raw_address,
                "cluster_id": cluster.cluster_id,
                "signals":    lot.signals,
                "strategies": lot.strategies,
                "source":     f"{lot.source_file}:row{lot.source_row}",
            })

    return deal_records


def feed_ownership_graph(lots: list[LotLead]) -> list[dict]:
    """Emit ownership-graph compatible node dicts."""
    return [
        {
            "node_type":  "lot",
            "node_id":    lot.lot_id,
            "address":    lot.raw_address,
            "broker":     lot.broker.name,
            "broker_phone": lot.broker.phone,
            "broker_email": lot.broker.email,
            "signals":    lot.signals,
            "price_usd":  lot.price_usd,
            "size_acres": lot.size_acres,
            "source":     f"{lot.source_file}:row{lot.source_row}",
        }
        for lot in lots
    ]


def feed_portfolio_distress(clusters: list[LotCluster]) -> list[dict]:
    """Flag probate clusters for portfolio-distress-analysis."""
    return [
        {
            "cluster_id":     c.cluster_id,
            "street":         c.street_full,
            "lot_count":      c.lot_count,
            "signals":        c.all_signals,
            "distress_flags": [s for s in c.all_signals if s in ("probate", "fenced")],
            "motivation_signals": [
                e["details"][:100] for e in c.evidence if "probate" in e.get("signals", [])
            ],
        }
        for c in clusters
        if "probate" in c.all_signals
    ]


# ── Output writers ────────────────────────────────────────────────────────────

def _dataclass_to_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _dataclass_to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_dataclass_to_dict(i) for i in obj]
    if isinstance(obj, tuple):
        return list(obj)
    return obj


def write_infill_clusters(clusters: list[LotCluster]) -> Path:
    out = OUT_DIR / "INFILL_CLUSTERS.json"
    payload = {
        "_meta": {
            "description": "Geo-clustered infill lot leads",
            "generated":   datetime.now(timezone.utc).isoformat(),
            "total_clusters": len(clusters),
            "total_lots":     sum(c.lot_count for c in clusters),
        },
        "clusters": [_dataclass_to_dict(c) for c in clusters],
    }
    out.write_text(json.dumps(payload, indent=2))
    return out


def write_builder_corridors(corridors: list[BuilderCorridor]) -> Path:
    out = OUT_DIR / "BUILDER_CORRIDORS.json"
    payload = {
        "_meta": {
            "description": "Builder corridors — streets with 3+ clustered lots",
            "generated":   datetime.now(timezone.utc).isoformat(),
            "total_corridors": len(corridors),
        },
        "corridors": [_dataclass_to_dict(c) for c in corridors],
    }
    out.write_text(json.dumps(payload, indent=2))
    return out


def write_assemblage_md(
    clusters: list[LotCluster],
    corridors: list[BuilderCorridor],
    lots: list[LotLead],
    deal_records: list[dict],
) -> Path:
    out  = OUT_DIR / "LOT_ASSEMBLAGE_OPPORTUNITIES.md"
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    high = [c for c in corridors if c.confidence == "high"]
    med  = [c for c in corridors if c.confidence == "medium"]

    # Broker frequency table
    broker_counts: dict[str, dict] = {}
    for lot in lots:
        bn = lot.broker.name
        if bn not in broker_counts:
            broker_counts[bn] = {"count": 0, "phone": lot.broker.phone, "email": lot.broker.email}
        broker_counts[bn]["count"] += 1

    broker_rows = "\n".join(
        f"| {name} | {info['count']} | "
        f"{'high' if info['count'] >= 4 else 'medium' if info['count'] >= 2 else 'low'} | "
        f"`{info['phone']}` | `{info['email']}` |"
        for name, info in sorted(broker_counts.items(), key=lambda x: -x[1]["count"])
    )

    # Corridor detail blocks
    corr_blocks = ""
    for corr in corridors:
        badge = "🔥 HIGH CONFIDENCE" if corr.confidence == "high" else (
                "⚡ MEDIUM CONFIDENCE" if corr.confidence == "medium" else "📍 LOW CONFIDENCE")
        price_lo = f"${corr.price_range[0]:,}" if corr.price_range[0] else "n/a"
        price_hi = f"${corr.price_range[1]:,}" if corr.price_range[1] else "n/a"
        strat_str = ", ".join(f"`{s}`" for s in corr.strategies) or "—"
        sig_str   = ", ".join(f"`{s}`" for s in corr.signals) or "—"
        corr_blocks += f"""
### {corr.street_full} — {badge}

| Field | Value |
|---|---|
| Corridor ID | `{corr.corridor_id}` |
| District | {corr.district} |
| Total Lots | {corr.total_lots} |
| Total Acres | {corr.total_acres} |
| Price Range | {price_lo} – {price_hi} |
| Assemblage Potential | **{corr.assemblage_potential.upper()}** |
| Confidence Score | {corr.confidence_score}/100 |
| Dominant Broker | {corr.dominant_broker} |
| Broker Dispo Confidence | {corr.broker_dispo_confidence} |
| Strategies | {strat_str} |
| Signals | {sig_str} |
| Evidence Files | {", ".join(f"`{f}`" for f in corr.evidence_files)} |

**Clusters:** {", ".join(f"`{cid}`" for cid in corr.cluster_ids)}

"""

    # High-assemblage cluster table
    high_asmb = [c for c in clusters if c.assemblage_potential == "high"]
    asmb_rows = "\n".join(
        f"| `{c.cluster_id}` | {c.street_full} | {c.lot_count} | {c.total_acres} ac | "
        f"${c.price_range[0]:,}–${c.price_range[1]:,} | "
        f"{', '.join(c.all_strategies[:3]) or '—'} |"
        for c in sorted(high_asmb, key=lambda x: -x.cluster_score)
    ) or "_None detected._"

    content = f"""# Lot Assemblage Opportunities

**Generated:** {now}
**Source:** `data/deal-leads/raw/`
**Total lots ingested:** {len(lots)}
**Total clusters:** {len(clusters)}
**Builder corridors detected:** {len(corridors)}

---

## Builder Corridors

{len(high)} HIGH confidence · {len(med)} MEDIUM confidence · {len(corridors) - len(high) - len(med)} LOW confidence
{corr_blocks}
---

## High-Assemblage Clusters

| Cluster | Street | Lots | Acres | Price Range | Strategies |
|---|---|---|---|---|---|
{asmb_rows}

---

## Broker Frequency & Dispo Confidence

| Broker | Listings | Dispo Confidence | Phone | Email |
|---|---|---|---|---|
{broker_rows}

---

## Strategy Signals Applied

| Strategy | Boost | Trigger Signals |
|---|---|---|
| `infill_build` | +15 | cleared_lot, utilities_available |
| `builder_assignment` | +20 | bishop_arts, trinity_groves, adjacent_lots |
| `land_flip` | +10 | probate |
| `corner_premium` | +5 | corner_lot |
| `assemblage_candidate` | +8 | adjacent_lots |

---

## Downstream Feeds

| Agent | Records Queued | Feed File |
|---|---|---|
| deal-scoring-engine | {len(deal_records)} | `data/deal-leads/INFILL_CLUSTERS.json` |
| ownership-graph | {len(lots)} | `data/deal-leads/INFILL_CLUSTERS.json` |
| portfolio-distress-analysis | {sum(1 for c in clusters if 'probate' in c.all_signals)} | distress-flagged clusters |

---

## Evidence Paths

| Path | Purpose |
|---|---|
| `data/deal-leads/raw/` | Source CSVs |
| `data/deal-leads/INFILL_CLUSTERS.json` | Geo-clustered lots |
| `data/deal-leads/BUILDER_CORRIDORS.json` | Detected corridors |
| `data/deal-scoring/HOT_BUYERS.json` | Buyer cross-reference |
| `data/deal-scoring/ACTIVE_BUYERS.json` | Buyer cross-reference |
| `data/deal-scoring/BUILDER_MATCHES.json` | Builder cross-reference |
"""

    out.write_text(content)
    return out


def write_timestamped_report(
    lots: list[LotLead],
    clusters: list[LotCluster],
    corridors: list[BuilderCorridor],
    run_ts: datetime,
) -> Path:
    stamp      = run_ts.strftime("%Y%m%dT%H%M%SZ")
    report_dir = REPORTS_DIR / stamp
    report_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "run_at":      run_ts.isoformat(),
        "lots_ingested": len(lots),
        "clusters":    len(clusters),
        "corridors":   len(corridors),
        "high_confidence_corridors": sum(1 for c in corridors if c.confidence == "high"),
        "sources":     sorted(set(l.source_file for l in lots)),
    }
    (report_dir / "RUN_SUMMARY.json").write_text(json.dumps(summary, indent=2))
    return report_dir


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    run_ts = datetime.now(timezone.utc)

    print("=" * 64)
    print("  AI_BRAIN LOT INGESTION PIPELINE")
    print(f"  Source: {RAW_DIR.relative_to(ROOT)}")
    print("=" * 64)
    print()

    # 1. Ingest
    print("[ 1 / 6 ] Ingesting CSVs ...")
    lots = ingest_all(RAW_DIR)
    if not lots:
        print(f"  No CSVs found in {RAW_DIR} — nothing to do.")
        sys.exit(0)
    print(f"  Ingested {len(lots)} lots from {len(set(l.source_file for l in lots))} file(s)")
    print()

    # 2. Geo-cluster
    print("[ 2 / 6 ] Geo-clustering ...")
    clusters = geo_cluster(lots)
    print(f"  {len(clusters)} cluster(s) across {len(set(l.street_name for l in lots))} street(s)")
    print()

    # 3. Cross-reference buyers
    print("[ 3 / 6 ] Cross-referencing buyers ...")
    clusters = cross_reference_buyers(clusters, lots)
    print(f"  Done (HOT_BUYERS / ACTIVE_BUYERS / BUILDER_MATCHES loaded if present)")
    print()

    # 4. Detect corridors
    print("[ 4 / 6 ] Detecting builder corridors ...")
    corridors = detect_corridors(clusters, lots)
    for corr in corridors:
        icon = "🔥" if corr.confidence == "high" else ("⚡" if corr.confidence == "medium" else "📍")
        print(f"  {icon} {corr.street_full:<30} {corr.total_lots} lots  {corr.confidence.upper()} ({corr.confidence_score}/100)")
    print()

    # 5. Feed downstream agents
    print("[ 5 / 6 ] Preparing downstream feeds ...")
    deal_records = feed_deal_scoring(clusters, lots)
    graph_nodes  = feed_ownership_graph(lots)
    distress_feed= feed_portfolio_distress(clusters)
    print(f"  deal-scoring-engine:        {len(deal_records)} deal records")
    print(f"  ownership-graph:            {len(graph_nodes)} lot nodes")
    print(f"  portfolio-distress-analysis:{len(distress_feed)} distress-flagged clusters")
    print()

    # 6. Write outputs
    print("[ 6 / 6 ] Writing outputs ...")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    clusters_path  = write_infill_clusters(clusters)
    corridors_path = write_builder_corridors(corridors)
    asmb_path      = write_assemblage_md(clusters, corridors, lots, deal_records)
    report_dir     = write_timestamped_report(lots, clusters, corridors, run_ts)
    print(f"  {clusters_path.relative_to(ROOT)}")
    print(f"  {corridors_path.relative_to(ROOT)}")
    print(f"  {asmb_path.relative_to(ROOT)}")
    print(f"  {report_dir.relative_to(ROOT)}/")
    print()

    # Summary
    high_corr  = [c for c in corridors if c.confidence == "high"]
    print("=" * 64)
    print(f"  Lots ingested:     {len(lots)}")
    print(f"  Clusters:          {len(clusters)}")
    print(f"  Builder corridors: {len(corridors)}")
    print(f"  High confidence:   {len(high_corr)}")
    if high_corr:
        print()
        print("  HIGH CONFIDENCE CORRIDORS:")
        for c in high_corr:
            asmb = c.assemblage_potential.upper()
            print(f"    🔥 {c.street_full} — {c.total_lots} lots — assemblage: {asmb}")
            print(f"       district: {c.district}  score: {c.confidence_score}/100")
            print(f"       broker:   {c.dominant_broker} ({c.broker_dispo_confidence} dispo confidence)")
    print("=" * 64)
    print()


if __name__ == "__main__":
    main()
