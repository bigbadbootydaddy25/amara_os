#!/usr/bin/env python3
"""
Record research module: discover, classify, and route public records to downstream agents.
Every record target must have source URL. No login bypass, no scraping.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Optional

from source_discovery import OSINT_SOURCES, OSINTSource


# ---------------------------------------------------------------------------
# Downstream agent routing registry
# ---------------------------------------------------------------------------

AGENT_ROUTING: dict[str, list[str]] = {
    # record_type → list of downstream agent IDs that consume this data
    "deed": [
        "buyer-activity-osint",
        "deal-discovery",
        "title-chain-analysis",
    ],
    "lien": [
        "deal-discovery",
        "title-chain-analysis",
        "risk-assessment",
    ],
    "permit": [
        "builder-verification",
        "property-condition",
        "deal-discovery",
    ],
    "tax_delinquent": [
        "deal-discovery",
        "risk-assessment",
        "distress-scoring",
    ],
    "code_violation": [
        "property-condition",
        "risk-assessment",
        "distress-scoring",
    ],
    "foreclosure": [
        "deal-discovery",
        "distress-scoring",
        "buyer-activity-osint",
    ],
    "entity": [
        "buyer-activity-osint",
        "builder-verification",
        "risk-assessment",
    ],
    "license": [
        "builder-verification",
        "contractor-verification",
    ],
    "court": [
        "risk-assessment",
        "title-chain-analysis",
    ],
    "gis": [
        "property-condition",
        "deal-discovery",
        "zoning-analysis",
    ],
    "bankruptcy": [
        "deal-discovery",
        "distress-scoring",
        "risk-assessment",
    ],
    "auction": [
        "deal-discovery",
        "buyer-activity-osint",
        "distress-scoring",
    ],
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class RecordTarget:
    record_id: str
    record_type: str            # deed|lien|permit|tax_delinquent|code_violation|foreclosure|entity|license|court|gis|bankruptcy|auction
    subject: str                # entity name or property address being researched
    source_id: str              # maps to OSINTSource.source_id
    url: Optional[str] = None
    access_type: str = "browser-only"
    status: str = "public_csv"  # public_csv|browser_only|login_required|paid|unavailable
    evidence_level: str = "possible"  # verified|probable|possible|flagged
    citations: list[str] = field(default_factory=list)
    linked_to: list[str] = field(default_factory=list)   # downstream agent IDs
    timestamp: str = ""
    notes: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = date.today().isoformat()
        if not self.linked_to:
            self.linked_to = AGENT_ROUTING.get(self.record_type, [])

    def add_citation(self, url: str) -> None:
        if url and url not in self.citations:
            self.citations.append(url)


def _access_to_status(access_type: str) -> str:
    mapping = {
        "csv": "public_csv",
        "pdf": "browser_only",
        "api": "public_csv",
        "browser-only": "browser_only",
        "manual": "browser_only",
        "login-required": "login_required",
        "paid": "paid",
    }
    return mapping.get(access_type, "browser_only")


# ---------------------------------------------------------------------------
# Record target builders
# ---------------------------------------------------------------------------

def _source_lookup() -> dict[str, OSINTSource]:
    return {s.source_id: s for s in OSINT_SOURCES}


def build_deed_targets(subject: str, county: str = "Dallas County") -> list[RecordTarget]:
    """Build deed record targets for a buyer entity or property address."""
    src_map = _source_lookup()
    targets = []
    priority_sources = ["TX-DAL-CLERK-001", "TX-TAR-CLERK-001", "TX-COL-CLERK-001"]
    for sid in priority_sources:
        src = src_map.get(sid)
        if not src:
            continue
        if county.lower() not in src.jurisdiction.lower() and county != "All":
            continue
        rt = RecordTarget(
            record_id=f"DEED-{sid}-{_slugify(subject)}",
            record_type="deed",
            subject=subject,
            source_id=sid,
            url=src.url,
            access_type=src.access_type,
            status=_access_to_status(src.access_type),
            evidence_level="probable",
        )
        rt.add_citation(src.url)
        targets.append(rt)
    return targets


def build_entity_targets(entity_name: str) -> list[RecordTarget]:
    """Build SOS/franchise-tax record targets for an entity name."""
    src_map = _source_lookup()
    targets = []
    for sid in ["TX-SOS-001", "TX-CPA-COA-001"]:
        src = src_map.get(sid)
        if not src:
            continue
        rt = RecordTarget(
            record_id=f"ENTITY-{sid}-{_slugify(entity_name)}",
            record_type="entity",
            subject=entity_name,
            source_id=sid,
            url=src.url,
            access_type=src.access_type,
            status=_access_to_status(src.access_type),
            evidence_level="probable",
        )
        rt.add_citation(src.url)
        targets.append(rt)
    return targets


def build_tax_delinquent_targets(subject: str) -> list[RecordTarget]:
    src_map = _source_lookup()
    targets = []
    for sid in ["TX-DAL-TAX-001", "TX-DAL-TAXDELINQ-001"]:
        src = src_map.get(sid)
        if not src:
            continue
        rt = RecordTarget(
            record_id=f"TAXDELINQ-{sid}-{_slugify(subject)}",
            record_type="tax_delinquent",
            subject=subject,
            source_id=sid,
            url=src.url,
            access_type=src.access_type,
            status=_access_to_status(src.access_type),
            evidence_level="possible",
        )
        rt.add_citation(src.url)
        targets.append(rt)
    return targets


def build_permit_targets(subject: str) -> list[RecordTarget]:
    src_map = _source_lookup()
    src = src_map.get("TX-DAL-PERMIT-001")
    if not src:
        return []
    rt = RecordTarget(
        record_id=f"PERMIT-{src.source_id}-{_slugify(subject)}",
        record_type="permit",
        subject=subject,
        source_id=src.source_id,
        url=src.url,
        access_type=src.access_type,
        status=_access_to_status(src.access_type),
        evidence_level="possible",
    )
    rt.add_citation(src.url)
    return [rt]


def build_code_violation_targets(subject: str) -> list[RecordTarget]:
    src_map = _source_lookup()
    src = src_map.get("TX-DAL-CODE-001")
    if not src:
        return []
    rt = RecordTarget(
        record_id=f"CODE-{src.source_id}-{_slugify(subject)}",
        record_type="code_violation",
        subject=subject,
        source_id=src.source_id,
        url=src.url,
        access_type=src.access_type,
        status=_access_to_status(src.access_type),
        evidence_level="possible",
    )
    rt.add_citation(src.url)
    return [rt]


def build_foreclosure_targets(subject: str) -> list[RecordTarget]:
    src_map = _source_lookup()
    targets = []
    for sid in ["TX-DAL-TRUSTEE-001", "TX-DAL-AUCTION-001"]:
        src = src_map.get(sid)
        if not src:
            continue
        rt = RecordTarget(
            record_id=f"FC-{sid}-{_slugify(subject)}",
            record_type="foreclosure",
            subject=subject,
            source_id=sid,
            url=src.url,
            access_type=src.access_type,
            status=_access_to_status(src.access_type),
            evidence_level="possible",
        )
        rt.add_citation(src.url)
        targets.append(rt)
    return targets


def build_license_targets(subject: str) -> list[RecordTarget]:
    src_map = _source_lookup()
    targets = []
    for sid in ["TX-TREC-001", "TX-TDLR-001"]:
        src = src_map.get(sid)
        if not src:
            continue
        rt = RecordTarget(
            record_id=f"LIC-{sid}-{_slugify(subject)}",
            record_type="license",
            subject=subject,
            source_id=sid,
            url=src.url,
            access_type=src.access_type,
            status=_access_to_status(src.access_type),
            evidence_level="possible",
        )
        rt.add_citation(src.url)
        targets.append(rt)
    return targets


def build_all_targets_for_subject(
    subject: str,
    subject_type: str = "entity",  # "entity" | "property"
    county: str = "Dallas County",
) -> list[RecordTarget]:
    """Build the full set of record targets for a subject."""
    targets: list[RecordTarget] = []
    if subject_type == "entity":
        targets += build_entity_targets(subject)
        targets += build_deed_targets(subject, county)
        targets += build_license_targets(subject)
        targets += build_foreclosure_targets(subject)
    elif subject_type == "property":
        targets += build_deed_targets(subject, county)
        targets += build_tax_delinquent_targets(subject)
        targets += build_permit_targets(subject)
        targets += build_code_violation_targets(subject)
        targets += build_foreclosure_targets(subject)
    return targets


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_record_source_targets(targets: list[RecordTarget], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = {
        "generated": date.today().isoformat(),
        "total_targets": len(targets),
        "by_record_type": _group_by(targets, "record_type"),
        "by_status": _group_by(targets, "status"),
        "targets": [asdict(t) for t in targets],
    }
    (reports_dir / "RECORD_SOURCE_TARGETS.json").write_text(json.dumps(out, indent=2))


def write_agent_routing(targets: list[RecordTarget], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    routing: dict[str, list[dict]] = {}
    for t in targets:
        for agent_id in t.linked_to:
            routing.setdefault(agent_id, []).append(
                {
                    "record_id": t.record_id,
                    "record_type": t.record_type,
                    "subject": t.subject,
                    "source_id": t.source_id,
                    "url": t.url,
                    "access_type": t.access_type,
                    "status": t.status,
                    "evidence_level": t.evidence_level,
                }
            )
    out = {
        "generated": date.today().isoformat(),
        "agents": routing,
    }
    (reports_dir / "OSINT_TO_AGENT_ROUTING.json").write_text(json.dumps(out, indent=2))


def _group_by(targets: list[RecordTarget], attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in targets:
        k = str(getattr(t, attr))
        counts[k] = counts.get(k, 0) + 1
    return dict(sorted(counts.items()))


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", s.lower())[:40]
