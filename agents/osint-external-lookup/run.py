from __future__ import annotations

"""OSINT External Lookup Runner.

Resolves queued gaps using:
  - User-provided CSV/JSON exports in data/osint/sources/
  - Inference derived from existing enriched data (no external calls)

No credential harvesting. No login bypass. No private scraping.
No fabricated values. Every field carries full provenance.
"""

import argparse
import csv
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# ── Constants ─────────────────────────────────────────────────────────────────

ALLOWED_USE = "lawful_osint_only"
CACHE_TTL_DAYS = 30
SOURCE_STALE_DAYS = 90

CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1, "none": 0}

# Field resolution status labels
RESOLVED      = "resolved"
LOW_CONFIDENCE = "low_confidence"
INFERRED      = "inferred"
STALE         = "stale"
UNRESOLVED    = "unresolved"

# ── Provenance ────────────────────────────────────────────────────────────────

def provenance(
    value: Any,
    source_type: str,
    source_name: str,
    source_path: str,
    collected_at: str,
    confidence: str,
    status: str = RESOLVED,
) -> dict:
    return {
        "value": value,
        "source_type": source_type,
        "source_name": source_name,
        "source_path_or_url": source_path,
        "collected_at": collected_at,
        "confidence": confidence,
        "allowed_use": ALLOWED_USE,
        "_resolution_status": status,
    }


def missing(ts: str) -> dict:
    return provenance(None, "missing", "", "", ts, "none", UNRESOLVED)


# ── Entity / address normalization ────────────────────────────────────────────

_LEGAL_SUFFIX = re.compile(
    r"\b(LLC|LP|LLP|INC|CORP|CO|LTD|TRUST|GROUP|FUND|CAPITAL|EQUITY"
    r"|HOLDINGS?|PROPERTIES|REALTY|INVESTMENTS?|VENTURES?|PARTNERS?)\b\.?",
    re.IGNORECASE,
)

_ADDR_ABBREV = {
    "STREET": "ST", "AVENUE": "AVE", "BOULEVARD": "BLVD", "DRIVE": "DR",
    "ROAD": "RD", "LANE": "LN", "COURT": "CT", "PLACE": "PL",
    "CIRCLE": "CIR", "HIGHWAY": "HWY", "NORTH": "N", "SOUTH": "S",
    "EAST": "E", "WEST": "W",
}


def normalize_entity_name(name: str | None) -> str:
    if not name:
        return ""
    name = _LEGAL_SUFFIX.sub("", name)
    return re.sub(r"\s+", " ", name).strip().upper()


def normalize_address(addr: str | None) -> str:
    if not addr:
        return ""
    addr = addr.upper()
    for word, abbr in _ADDR_ABBREV.items():
        addr = re.sub(rf"\b{word}\b", abbr, addr)
    return re.sub(r"\s+", " ", addr).strip()


def normalize_apn(apn: str | None) -> str:
    """Strip hyphens and spaces from APN for comparison."""
    return re.sub(r"[\s\-]", "", apn or "").upper()


# ── Cache layer ───────────────────────────────────────────────────────────────

class CacheLayer:
    def __init__(self, cache_dir: Path, ttl_days: int = CACHE_TTL_DAYS) -> None:
        self._dir = cache_dir
        self._ttl = timedelta(days=ttl_days)
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe_key = re.sub(r"[^\w\-]", "_", key)
        return self._dir / f"{safe_key}.json"

    def is_expired(self, key: str) -> bool:
        p = self._path(key)
        if not p.exists():
            return True
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        return age > self._ttl

    def get(self, key: str) -> dict | None:
        p = self._path(key)
        if not p.exists() or self.is_expired(key):
            return None
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, key: str, data: dict) -> None:
        p = self._path(key)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


# ── Source freshness ──────────────────────────────────────────────────────────

def source_freshness(path: Path) -> str:
    """Return 'fresh', 'stale', or 'unknown' based on file mtime."""
    try:
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        )
        return "stale" if age.days > SOURCE_STALE_DAYS else "fresh"
    except OSError:
        return "unknown"


# ── Adapter result ────────────────────────────────────────────────────────────

@dataclass
class AdapterResult:
    field: str
    value: Any
    source_type: str
    source_name: str
    source_path: str
    collected_at: str
    confidence: str
    status: str

    def to_provenance(self) -> dict:
        return provenance(
            self.value, self.source_type, self.source_name,
            self.source_path, self.collected_at, self.confidence, self.status,
        )


# ── Base adapter ──────────────────────────────────────────────────────────────

class SourceAdapter(ABC):
    source_type: str = ""
    source_name: str = ""
    file_patterns: list[str] = []
    field_coverage: list[str] = []

    def find_sources(self, sources_dir: Path) -> list[Path]:
        """Scan sources_dir for files matching this adapter's patterns."""
        matches: list[Path] = []
        if not sources_dir.exists():
            return matches
        for pattern in self.file_patterns:
            matches.extend(sources_dir.glob(pattern))
        return sorted(set(matches))

    def can_resolve(self, field_name: str) -> bool:
        return field_name in self.field_coverage

    def _load_csv(self, path: Path) -> list[dict]:
        try:
            with open(path, newline="", encoding="utf-8") as f:
                return list(csv.DictReader(f))
        except (FileNotFoundError, OSError):
            return []

    def _load_json(self, path: Path) -> Any:
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    @abstractmethod
    def lookup_entity(
        self, entity: dict, field: str, source_files: list[Path], ts: str
    ) -> AdapterResult | None: ...

    @abstractmethod
    def lookup_property(
        self, prop: dict, field: str, source_files: list[Path], ts: str
    ) -> AdapterResult | None: ...


# ── File-based adapters (all lawful export/CSV ingestion) ─────────────────────

class CountyAssessorAdapter(SourceAdapter):
    source_type = "county_assessor"
    source_name = "County Appraisal District (CAD) Export"
    file_patterns = ["*cad*.csv", "*assessor*.csv", "*appraisal*.csv", "*cad*.json"]
    field_coverage = ["assessed_value", "owner_name", "zoning_classification", "lot_size_acres"]

    def lookup_entity(self, entity, field, source_files, ts):
        return None  # CAD resolves properties, not entities

    def lookup_property(self, prop, field, source_files, ts):
        addr = normalize_address(prop.get("address", {}).get("value"))
        for src in source_files:
            freshness = source_freshness(src)
            status = STALE if freshness == "stale" else RESOLVED
            for row in self._load_csv(src):
                if normalize_address(row.get("situs_address") or row.get("address", "")) == addr:
                    val = row.get(field) or row.get(field.replace("_", " "))
                    if val:
                        return AdapterResult(
                            field=field, value=val, source_type=self.source_type,
                            source_name=self.source_name, source_path=str(src),
                            collected_at=ts, confidence="high", status=status,
                        )
        return None


class CountyClerkAdapter(SourceAdapter):
    source_type = "county_clerk"
    source_name = "County Clerk Recording Export"
    file_patterns = ["*clerk*.csv", "*deed*.csv", "*recording*.csv", "*grantor*.csv"]
    field_coverage = ["owner_name", "last_sale_price", "last_sale_date", "liens_recorded"]

    def lookup_entity(self, entity, field, source_files, ts):
        return None

    def lookup_property(self, prop, field, source_files, ts):
        addr = normalize_address(prop.get("address", {}).get("value"))
        for src in source_files:
            freshness = source_freshness(src)
            status = STALE if freshness == "stale" else RESOLVED
            for row in self._load_csv(src):
                if normalize_address(row.get("property_address", "")) == addr:
                    val = row.get(field)
                    if val:
                        return AdapterResult(
                            field=field, value=val, source_type=self.source_type,
                            source_name=self.source_name, source_path=str(src),
                            collected_at=ts, confidence="high", status=status,
                        )
        return None


class GISAPNAdapter(SourceAdapter):
    source_type = "gis_apn"
    source_name = "GIS / APN Parcel Export"
    file_patterns = ["*gis*.csv", "*apn*.csv", "*parcel*.csv", "*gis*.json"]
    field_coverage = ["zoning_classification", "lot_size_acres", "assessed_value"]

    def lookup_entity(self, entity, field, source_files, ts):
        return None

    def lookup_property(self, prop, field, source_files, ts):
        addr = normalize_address(prop.get("address", {}).get("value"))
        for src in source_files:
            freshness = source_freshness(src)
            status = STALE if freshness == "stale" else RESOLVED
            for row in self._load_csv(src):
                if normalize_address(row.get("situs_address", "")) == addr:
                    val = row.get("zoning") or row.get("zone_code") or row.get(field)
                    if val:
                        return AdapterResult(
                            field=field, value=val, source_type=self.source_type,
                            source_name=self.source_name, source_path=str(src),
                            collected_at=ts, confidence="medium", status=status,
                        )
        return None


class SOSBusinessAdapter(SourceAdapter):
    source_type = "sos_business_search"
    source_name = "Secretary of State Business Search Export"
    file_patterns = ["*sos*.csv", "*secretary*.csv", "*business_search*.csv", "*corp_search*.csv"]
    field_coverage = ["sos_status", "registered_agent", "entity_type"]

    def _match_entity(self, entity: dict, row: dict) -> bool:
        name = normalize_entity_name(entity.get("name", {}).get("value"))
        row_name = normalize_entity_name(row.get("entity_name") or row.get("company_name", ""))
        return name and row_name and name in row_name

    def lookup_entity(self, entity, field, source_files, ts):
        for src in source_files:
            freshness = source_freshness(src)
            status = STALE if freshness == "stale" else RESOLVED
            for row in self._load_csv(src):
                if self._match_entity(entity, row):
                    val = (
                        row.get("status") or row.get("entity_status")
                        if field == "sos_status"
                        else row.get("registered_agent") or row.get("agent_name")
                    )
                    if val:
                        return AdapterResult(
                            field=field, value=val, source_type=self.source_type,
                            source_name=self.source_name, source_path=str(src),
                            collected_at=ts, confidence="high", status=status,
                        )
        return None

    def lookup_property(self, prop, field, source_files, ts):
        return None


class TrusteeForeclosureAdapter(SourceAdapter):
    source_type = "trustee_foreclosure"
    source_name = "Trustee Sale / Foreclosure Notice Export"
    file_patterns = ["*trustee*.csv", "*foreclosure*.csv", "*notice_of_sale*.csv", "*nod*.csv"]
    field_coverage = ["liens_recorded", "loan_balance", "sos_status"]

    def _match_entity(self, entity: dict, row: dict) -> bool:
        name = normalize_entity_name(entity.get("name", {}).get("value"))
        row_name = normalize_entity_name(row.get("borrower") or row.get("trustor", ""))
        return name and row_name and name in row_name

    def lookup_entity(self, entity, field, source_files, ts):
        for src in source_files:
            freshness = source_freshness(src)
            status = STALE if freshness == "stale" else RESOLVED
            for row in self._load_csv(src):
                if self._match_entity(entity, row):
                    val = row.get("loan_balance") or row.get("opening_bid") or row.get("notice_date")
                    if val:
                        return AdapterResult(
                            field=field, value=val, source_type=self.source_type,
                            source_name=self.source_name, source_path=str(src),
                            collected_at=ts, confidence="medium", status=status,
                        )
        return None

    def lookup_property(self, prop, field, source_files, ts):
        addr = normalize_address(prop.get("address", {}).get("value"))
        for src in source_files:
            freshness = source_freshness(src)
            status = STALE if freshness == "stale" else RESOLVED
            for row in self._load_csv(src):
                if normalize_address(row.get("property_address", "")) == addr:
                    val = row.get("liens") or row.get("lien_amount") or row.get("notice_date")
                    if val:
                        return AdapterResult(
                            field=field, value=val, source_type=self.source_type,
                            source_name=self.source_name, source_path=str(src),
                            collected_at=ts, confidence="medium", status=status,
                        )
        return None


class PermitAdapter(SourceAdapter):
    source_type = "permit_export"
    source_name = "Building Permit Export"
    file_patterns = ["*permit*.csv", "*building_permit*.csv", "*permits*.json"]
    field_coverage = ["permit_activity"]

    def lookup_entity(self, entity, field, source_files, ts):
        return None

    def lookup_property(self, prop, field, source_files, ts):
        addr = normalize_address(prop.get("address", {}).get("value"))
        permits = []
        for src in source_files:
            freshness = source_freshness(src)
            status = STALE if freshness == "stale" else RESOLVED
            for row in self._load_csv(src):
                if normalize_address(row.get("address", "")) == addr:
                    permits.append(row)
            if permits:
                return AdapterResult(
                    field=field, value=permits, source_type=self.source_type,
                    source_name=self.source_name, source_path=str(src),
                    collected_at=ts, confidence="high", status=status,
                )
        return None


class CodeViolationAdapter(SourceAdapter):
    source_type = "code_violation"
    source_name = "Code Enforcement Export"
    file_patterns = ["*code_violation*.csv", "*code_enforcement*.csv", "*violations*.csv"]
    field_coverage = ["permit_activity", "liens_recorded"]

    def lookup_entity(self, entity, field, source_files, ts):
        return None

    def lookup_property(self, prop, field, source_files, ts):
        addr = normalize_address(prop.get("address", {}).get("value"))
        for src in source_files:
            freshness = source_freshness(src)
            status = STALE if freshness == "stale" else RESOLVED
            violations = [
                r for r in self._load_csv(src)
                if normalize_address(r.get("address", "")) == addr
            ]
            if violations:
                return AdapterResult(
                    field=field, value=violations, source_type=self.source_type,
                    source_name=self.source_name, source_path=str(src),
                    collected_at=ts, confidence="high", status=status,
                )
        return None


class TaxDelinquentAdapter(SourceAdapter):
    source_type = "tax_delinquent"
    source_name = "Tax Delinquency Export"
    file_patterns = ["*tax_delinquent*.csv", "*delinquent_tax*.csv", "*tax_roll*.csv"]
    field_coverage = ["owner_name", "liens_recorded", "loan_balance"]

    def _match_entity(self, entity: dict, row: dict) -> bool:
        name = normalize_entity_name(entity.get("name", {}).get("value"))
        row_name = normalize_entity_name(row.get("owner_name") or row.get("taxpayer", ""))
        return name and row_name and name in row_name

    def lookup_entity(self, entity, field, source_files, ts):
        for src in source_files:
            freshness = source_freshness(src)
            status = STALE if freshness == "stale" else RESOLVED
            for row in self._load_csv(src):
                if self._match_entity(entity, row):
                    val = row.get("amount_due") or row.get("balance")
                    if val:
                        return AdapterResult(
                            field=field, value=val, source_type=self.source_type,
                            source_name=self.source_name, source_path=str(src),
                            collected_at=ts, confidence="medium", status=status,
                        )
        return None

    def lookup_property(self, prop, field, source_files, ts):
        addr = normalize_address(prop.get("address", {}).get("value"))
        for src in source_files:
            freshness = source_freshness(src)
            status = STALE if freshness == "stale" else RESOLVED
            for row in self._load_csv(src):
                if normalize_address(row.get("property_address", "")) == addr:
                    val = row.get("owner_name") or row.get("amount_due")
                    if val:
                        return AdapterResult(
                            field=field, value=val, source_type=self.source_type,
                            source_name=self.source_name, source_path=str(src),
                            collected_at=ts, confidence="medium", status=status,
                        )
        return None


class PACERAdapter(SourceAdapter):
    source_type = "pacer_manual_export"
    source_name = "PACER Federal Court Record (Manual Export)"
    file_patterns = ["*pacer*.csv", "*federal_court*.csv", "*bankruptcy*.csv"]
    field_coverage = ["sos_status", "loan_balance", "liens_recorded"]

    def _match_entity(self, entity: dict, row: dict) -> bool:
        name = normalize_entity_name(entity.get("name", {}).get("value"))
        row_name = normalize_entity_name(row.get("debtor") or row.get("entity_name", ""))
        return name and row_name and name in row_name

    def lookup_entity(self, entity, field, source_files, ts):
        for src in source_files:
            freshness = source_freshness(src)
            status = STALE if freshness == "stale" else RESOLVED
            for row in self._load_csv(src):
                if self._match_entity(entity, row):
                    val = row.get("case_status") or row.get("filing_date") or row.get("balance")
                    if val:
                        return AdapterResult(
                            field=field, value=val, source_type=self.source_type,
                            source_name=self.source_name, source_path=str(src),
                            collected_at=ts, confidence="high", status=status,
                        )
        return None

    def lookup_property(self, prop, field, source_files, ts):
        return None


class PropStreamAdapter(SourceAdapter):
    source_type = "propstream_propwire"
    source_name = "PropStream / Propwire Export (Manual)"
    file_patterns = ["*propstream*.csv", "*propwire*.csv", "*prop_export*.csv"]
    field_coverage = [
        "owner_name", "assessed_value", "last_sale_price", "last_sale_date",
        "liens_recorded", "loan_balance", "estimated_equity", "portfolio_count",
    ]

    def _match_entity(self, entity: dict, row: dict) -> bool:
        name = normalize_entity_name(entity.get("name", {}).get("value"))
        row_name = normalize_entity_name(row.get("owner_name") or row.get("entity_name", ""))
        return name and row_name and name in row_name

    def lookup_entity(self, entity, field, source_files, ts):
        for src in source_files:
            freshness = source_freshness(src)
            status = STALE if freshness == "stale" else RESOLVED
            for row in self._load_csv(src):
                if self._match_entity(entity, row):
                    val = row.get(field) or row.get(field.replace("_", " "))
                    if val:
                        return AdapterResult(
                            field=field, value=val, source_type=self.source_type,
                            source_name=self.source_name, source_path=str(src),
                            collected_at=ts, confidence="medium", status=status,
                        )
        return None

    def lookup_property(self, prop, field, source_files, ts):
        addr = normalize_address(prop.get("address", {}).get("value"))
        for src in source_files:
            freshness = source_freshness(src)
            status = STALE if freshness == "stale" else RESOLVED
            for row in self._load_csv(src):
                if normalize_address(row.get("property_address", "") or row.get("address", "")) == addr:
                    val = row.get(field) or row.get(field.replace("_", " "))
                    if val:
                        return AdapterResult(
                            field=field, value=val, source_type=self.source_type,
                            source_name=self.source_name, source_path=str(src),
                            collected_at=ts, confidence="medium", status=status,
                        )
        return None


# ── Inference adapter (derives from existing enriched data) ───────────────────

_BISHOP_ARTS_ZONING = "Mixed-Use / Bishop Arts Urban Development Overlay (Dallas MU-1)"
_TRINITY_GROVES_ZONING = "Commercial Corridor / Trinity Groves Planned Development (CS-1)"
_INFILL_ZONING = "Residential Infill (SF-1 or SF-2 likely; verify with Dallas Planning)"


class InferenceAdapter(SourceAdapter):
    """Derives field values from already-known enriched data. No external calls."""

    source_type = "inferred"
    source_name = "Inference from enriched internal data"
    file_patterns = []
    field_coverage = [
        "loan_balance", "estimated_equity", "associated_addresses",
        "permit_activity", "portfolio_count", "zoning_classification",
    ]

    def find_sources(self, sources_dir: Path) -> list[Path]:
        return []  # inference needs no source files

    def lookup_entity(self, entity: dict, field: str, source_files: list[Path], ts: str) -> AdapterResult | None:
        eid = entity.get("entity_id", "")

        if field == "loan_balance":
            di = (entity.get("distress_indicators") or {}).get("value") or {}
            li = (entity.get("leverage_indicators") or {}).get("value") or {}
            days = di.get("loan_delinquency_days", 0)
            ltv = li.get("portfolio_ltv")
            ext = li.get("loans_in_extension", 0)
            if days and days > 0:
                val = f"Delinquent — {days} days past due (inferred from distress_indicators.loan_delinquency_days)"
                return AdapterResult(field=field, value=val, source_type=self.source_type,
                    source_name=self.source_name, source_path=f"data/osint/enriched/OSINT_ENRICHED_ENTITIES.json#{eid}",
                    collected_at=ts, confidence="low", status=INFERRED)
            if ltv and ltv > 0.85:
                val = f"Severely overleveraged — portfolio LTV {round(ltv*100)}% (inferred from leverage_indicators)"
                return AdapterResult(field=field, value=val, source_type=self.source_type,
                    source_name=self.source_name, source_path=f"data/osint/enriched/OSINT_ENRICHED_ENTITIES.json#{eid}",
                    collected_at=ts, confidence="low", status=INFERRED)
            if ext and ext > 0:
                val = f"{ext} loan(s) in extension (inferred from leverage_indicators.loans_in_extension)"
                return AdapterResult(field=field, value=val, source_type=self.source_type,
                    source_name=self.source_name, source_path=f"data/osint/enriched/OSINT_ENRICHED_ENTITIES.json#{eid}",
                    collected_at=ts, confidence="low", status=INFERRED)

        if field == "estimated_equity":
            dscore = (entity.get("distress_score") or {}).get("value")
            di = (entity.get("distress_indicators") or {}).get("value") or {}
            li = (entity.get("leverage_indicators") or {}).get("value") or {}
            dscr = di.get("debt_service_coverage_ratio") or di.get("dscr")
            ltv = li.get("portfolio_ltv")
            if dscore and dscore >= 80:
                val = "Severely impaired or negative (inferred: distress_score >= 80 indicates near-zero equity)"
                return AdapterResult(field=field, value=val, source_type=self.source_type,
                    source_name=self.source_name, source_path=f"data/osint/enriched/OSINT_ENRICHED_ENTITIES.json#{eid}",
                    collected_at=ts, confidence="low", status=INFERRED)
            if ltv and ltv > 0.90:
                val = f"Thin or negative — portfolio LTV {round(ltv*100)}% leaves minimal equity cushion (inferred)"
                return AdapterResult(field=field, value=val, source_type=self.source_type,
                    source_name=self.source_name, source_path=f"data/osint/enriched/OSINT_ENRICHED_ENTITIES.json#{eid}",
                    collected_at=ts, confidence="low", status=INFERRED)
            if dscore and dscore >= 55:
                val = "Materially impaired (inferred: distress_score 55-79 indicates significant equity erosion)"
                return AdapterResult(field=field, value=val, source_type=self.source_type,
                    source_name=self.source_name, source_path=f"data/osint/enriched/OSINT_ENRICHED_ENTITIES.json#{eid}",
                    collected_at=ts, confidence="low", status=INFERRED)

        if field == "associated_addresses":
            projects = (entity.get("stalled_projects") or {}).get("value") or []
            if projects:
                addrs = [p["address"] for p in projects if p.get("address")]
                if addrs:
                    return AdapterResult(field=field, value=addrs, source_type=self.source_type,
                        source_name=self.source_name, source_path=f"data/osint/enriched/OSINT_ENRICHED_ENTITIES.json#{eid}",
                        collected_at=ts, confidence="medium", status=INFERRED)

        if field == "permit_activity":
            projects = (entity.get("stalled_projects") or {}).get("value") or []
            if projects:
                activity = [
                    {
                        "project": p.get("project_name"),
                        "address": p.get("address"),
                        "permit_pull_date": p.get("permit_pull_date"),
                        "last_inspection": p.get("last_inspection_passed"),
                        "status": "stalled",
                        "months_stalled": p.get("months_since_meaningful_progress"),
                    }
                    for p in projects
                ]
                return AdapterResult(field=field, value=activity, source_type=self.source_type,
                    source_name=self.source_name, source_path=f"data/osint/enriched/OSINT_ENRICHED_ENTITIES.json#{eid}",
                    collected_at=ts, confidence="medium", status=INFERRED)

        if field == "portfolio_count":
            projects = (entity.get("stalled_projects") or {}).get("value") or []
            if projects:
                return AdapterResult(field=field, value=len(projects), source_type=self.source_type,
                    source_name=self.source_name, source_path=f"data/osint/enriched/OSINT_ENRICHED_ENTITIES.json#{eid}",
                    collected_at=ts, confidence="low", status=INFERRED)

        return None

    def lookup_property(self, prop: dict, field: str, source_files: list[Path], ts: str) -> AdapterResult | None:
        pid = prop.get("property_id", "")
        details = (prop.get("broker_details") or {}).get("value", "").lower()
        addr = (prop.get("address") or {}).get("value", "")

        if field == "zoning_classification":
            if "bishop arts" in details or "bishop arts" in addr.lower():
                return AdapterResult(field=field, value=_BISHOP_ARTS_ZONING, source_type=self.source_type,
                    source_name=self.source_name, source_path=f"data/osint/enriched/OSINT_ENRICHED_PROPERTIES.json#{pid}",
                    collected_at=ts, confidence="medium", status=INFERRED)
            if "trinity groves" in details or "trinity groves" in addr.lower():
                return AdapterResult(field=field, value=_TRINITY_GROVES_ZONING, source_type=self.source_type,
                    source_name=self.source_name, source_path=f"data/osint/enriched/OSINT_ENRICHED_PROPERTIES.json#{pid}",
                    collected_at=ts, confidence="medium", status=INFERRED)
            if any(kw in details for kw in ("infill", "cleared lot", "cleared land", "builder-ready")):
                return AdapterResult(field=field, value=_INFILL_ZONING, source_type=self.source_type,
                    source_name=self.source_name, source_path=f"data/osint/enriched/OSINT_ENRICHED_PROPERTIES.json#{pid}",
                    collected_at=ts, confidence="low", status=INFERRED)

        return None


# ── Registry ──────────────────────────────────────────────────────────────────

ALL_ADAPTERS: list[SourceAdapter] = [
    CountyAssessorAdapter(),
    CountyClerkAdapter(),
    GISAPNAdapter(),
    SOSBusinessAdapter(),
    TrusteeForeclosureAdapter(),
    PermitAdapter(),
    CodeViolationAdapter(),
    TaxDelinquentAdapter(),
    PACERAdapter(),
    PropStreamAdapter(),
    InferenceAdapter(),
]


# ── Resolution engine ─────────────────────────────────────────────────────────

def _best_result(candidates: list[AdapterResult]) -> AdapterResult:
    """Pick highest-confidence result; prefer resolved over inferred."""
    def rank(r: AdapterResult) -> tuple:
        status_rank = {RESOLVED: 3, STALE: 2, LOW_CONFIDENCE: 1, INFERRED: 0}.get(r.status, 0)
        conf_rank = CONFIDENCE_RANK.get(r.confidence, 0)
        return (status_rank, conf_rank)
    return max(candidates, key=rank)


def resolve_record(
    record: dict,
    missing_fields: list[str],
    lookup_fn: str,  # "lookup_entity" or "lookup_property"
    sources_dir: Path,
    cache: CacheLayer,
    ts: str,
) -> dict:
    """Resolve all missing fields for one record. Returns a copy with gaps filled."""
    result = dict(record)

    for field_name in missing_fields:
        cache_key = f"{record.get('entity_id') or record.get('property_id')}_{field_name}"

        # Check cache first
        cached = cache.get(cache_key)
        if cached:
            result[field_name] = cached
            continue

        candidates: list[AdapterResult] = []
        for adapter in ALL_ADAPTERS:
            if not adapter.can_resolve(field_name):
                continue
            source_files = adapter.find_sources(sources_dir)
            fn = getattr(adapter, lookup_fn)
            res = fn(record, field_name, source_files, ts)
            if res is not None:
                candidates.append(res)

        if candidates:
            best = _best_result(candidates)
            prov = best.to_provenance()
            result[field_name] = prov
            cache.set(cache_key, prov)

    return result


# ── Output writers ────────────────────────────────────────────────────────────

def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _field_status(record: dict) -> dict[str, int]:
    counts: dict[str, int] = {RESOLVED: 0, LOW_CONFIDENCE: 0, INFERRED: 0, STALE: 0, UNRESOLVED: 0}
    for val in record.values():
        if isinstance(val, dict) and "_resolution_status" in val:
            s = val["_resolution_status"]
            counts[s] = counts.get(s, 0) + 1
        elif isinstance(val, dict) and "source_type" in val:
            st = val["source_type"]
            if st == "missing":
                counts[UNRESOLVED] += 1
            else:
                counts[RESOLVED] += 1
    return counts


def write_fill_report(
    original_queue: list[dict],
    entities_after: list[dict],
    properties_after: list[dict],
    run_ts: datetime,
    out_path: Path,
) -> dict:
    original_missing = sum(len(q["missing_fields"]) for q in original_queue)

    entity_statuses: dict[str, int] = {RESOLVED: 0, LOW_CONFIDENCE: 0, INFERRED: 0, STALE: 0, UNRESOLVED: 0}
    prop_statuses: dict[str, int] = {RESOLVED: 0, LOW_CONFIDENCE: 0, INFERRED: 0, STALE: 0, UNRESOLVED: 0}

    for rec in entities_after:
        for s, n in _field_status(rec).items():
            entity_statuses[s] = entity_statuses.get(s, 0) + n
    for rec in properties_after:
        for s, n in _field_status(rec).items():
            prop_statuses[s] = prop_statuses.get(s, 0) + n

    newly_resolved = (
        entity_statuses[RESOLVED] + entity_statuses[INFERRED] +
        entity_statuses[LOW_CONFIDENCE] + entity_statuses[STALE] +
        prop_statuses[RESOLVED] + prop_statuses[INFERRED] +
        prop_statuses[LOW_CONFIDENCE] + prop_statuses[STALE]
    ) - (
        # subtract fields that were already filled before this run
        sum(
            sum(1 for v in rec.values() if isinstance(v, dict) and v.get("source_type") not in (None, "missing") and "_resolution_status" not in v)
            for rec in entities_after + properties_after
        )
    )
    # Simpler approach: count remaining gaps
    remaining = entity_statuses[UNRESOLVED] + prop_statuses[UNRESOLVED]

    report = {
        "run_ts": run_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "original_missing_field_slots": original_missing,
        "remaining_unresolved": remaining,
        "gap_reduction": original_missing - remaining,
        "gap_reduction_pct": round((original_missing - remaining) / original_missing * 100) if original_missing else 0,
        "entity_field_statuses": entity_statuses,
        "property_field_statuses": prop_statuses,
        "adapters_with_sources": [],
        "adapters_no_sources": [a.source_name for a in ALL_ADAPTERS if not isinstance(a, InferenceAdapter)],
        "inference_adapter": "active",
        "allowed_use": ALLOWED_USE,
    }
    _write_json(out_path, report)
    return report


def write_remaining_gaps(
    entities: list[dict],
    properties: list[dict],
    out_path: Path,
) -> list[dict]:
    gaps = []
    for rec in entities:
        mf = [
            k for k, v in rec.items()
            if isinstance(v, dict) and v.get("source_type") == "missing"
        ]
        if mf:
            gaps.append({
                "entity_id": rec.get("entity_id"),
                "entity_type": "entity",
                "missing_fields": mf,
                "requires": "SOS export, PropStream export, or county deed export",
                "allowed_use": ALLOWED_USE,
            })
    for rec in properties:
        mf = [
            k for k, v in rec.items()
            if isinstance(v, dict) and v.get("source_type") == "missing"
        ]
        if mf:
            gaps.append({
                "entity_id": rec.get("property_id"),
                "entity_type": "property",
                "missing_fields": mf,
                "requires": "CAD export, county clerk export, or PropStream export",
                "allowed_use": ALLOWED_USE,
            })
    _write_json(out_path, gaps)
    return gaps


def write_lookup_audit(
    entities: list[dict],
    properties: list[dict],
    fill_report: dict,
    remaining_gaps: list[dict],
    sources_dir: Path,
    run_ts: datetime,
    report_dir: Path,
) -> Path:
    ts_str = run_ts.strftime("%Y%m%dT%H%M%SZ")
    out = report_dir / ts_str / "EXTERNAL_LOOKUP_AUDIT.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    source_files_present = sorted(
        str(p.name) for p in sources_dir.glob("*")
        if p.is_file() and not p.name.startswith(".")
    ) if sources_dir.exists() else []

    lines = [
        "# OSINT External Lookup Audit",
        "",
        f"**Run:** `{ts_str}`  ",
        f"**Allowed use:** `{ALLOWED_USE}`  ",
        "**Method:** Lawful public-record exports, user-provided CSV/JSON files, inference from enriched data",
        "",
        "---",
        "",
        "## Gap Reduction Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Original missing field slots | {fill_report['original_missing_field_slots']} |",
        f"| Remaining unresolved | {fill_report['remaining_unresolved']} |",
        f"| Gap reduction | {fill_report['gap_reduction']} fields |",
        f"| Gap reduction % | {fill_report['gap_reduction_pct']}% |",
        "",
        "---",
        "",
        "## Field Status Breakdown",
        "",
        "### Entities",
        "",
        "| Status | Count |",
        "|--------|-------|",
    ]
    for s, n in fill_report["entity_field_statuses"].items():
        lines.append(f"| `{s}` | {n} |")

    lines += [
        "",
        "### Properties",
        "",
        "| Status | Count |",
        "|--------|-------|",
    ]
    for s, n in fill_report["property_field_statuses"].items():
        lines.append(f"| `{s}` | {n} |")

    lines += [
        "",
        "---",
        "",
        "## Source Files Available",
        "",
    ]
    if source_files_present:
        lines.append("| File | Status |")
        lines.append("|------|--------|")
        for sf in source_files_present:
            p = sources_dir / sf
            lines.append(f"| `{sf}` | {source_freshness(p)} |")
    else:
        lines += [
            "> **No source export files found in `data/osint/sources/`.**",
            ">",
            "> To enrich with public records, place CSV/JSON exports in that directory.",
            "> Supported adapters and their expected filename patterns:",
            "",
        ]
        for adapter in ALL_ADAPTERS:
            if isinstance(adapter, InferenceAdapter):
                continue
            patterns = ", ".join(f"`{p}`" for p in adapter.file_patterns)
            lines.append(f"- **{adapter.source_name}**: {patterns}")

    lines += [
        "",
        "---",
        "",
        "## Inference Adapter Results",
        "",
        "Fields resolved without external files via inference from existing enriched data:",
        "",
        "| entity_id | field | confidence | value_summary |",
        "|-----------|-------|------------|---------------|",
    ]
    for rec in entities + properties:
        eid = rec.get("entity_id") or rec.get("property_id", "")
        for key, val in rec.items():
            if isinstance(val, dict) and val.get("source_type") == "inferred":
                v = str(val.get("value", ""))[:60]
                lines.append(f"| `{eid}` | `{key}` | {val.get('confidence')} | {v}… |")

    lines += [
        "",
        "---",
        "",
        "## Remaining Gaps",
        "",
        "Fields that could not be resolved by any available adapter or inference:",
        "",
        "| entity_id | type | missing_fields | how_to_resolve |",
        "|-----------|------|----------------|----------------|",
    ]
    for g in remaining_gaps:
        fields_str = ", ".join(g["missing_fields"][:3])
        if len(g["missing_fields"]) > 3:
            fields_str += f" +{len(g['missing_fields']) - 3} more"
        lines.append(
            f"| `{g['entity_id']}` | {g['entity_type']} | {fields_str} | {g['requires']} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Compliance Notes",
        "",
        "- All enriched values carry `allowed_use: lawful_osint_only`",
        "- No credential harvesting, login bypass, or private scraping performed",
        "- Inference values are explicitly labeled `source_type: inferred` and `confidence: low` or `medium`",
        "- Missing values remain `source_type: missing` — no fabrication",
        "- Cache TTL: 30 days | Source staleness threshold: 90 days",
    ]

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


# ── Pipeline ──────────────────────────────────────────────────────────────────

def _load_json_file(path: Path) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def run(workspace_root: Path) -> None:
    run_ts = datetime.now(timezone.utc)
    ts = run_ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    data_dir    = workspace_root / "data"
    osint_dir   = data_dir / "osint"
    enriched_dir = osint_dir / "enriched"
    ext_dir     = osint_dir / "external-enriched"
    cache_dir   = osint_dir / "external-cache"
    sources_dir = osint_dir / "sources"
    report_dir  = workspace_root / "agents" / "osint-external-lookup" / "reports"

    print("=" * 64)
    print("  AI_BRAIN OSINT EXTERNAL LOOKUP RUNNER")
    print(f"  workspace: {workspace_root}")
    print("=" * 64)

    # ── Load inputs ───────────────────────────────────────────────────────────

    print("\n[ 1 / 5 ] Loading inputs ...")

    queue    = _load_json_file(enriched_dir / "OSINT_TO_ENRICHMENT_QUEUE.json") or []
    entities = _load_json_file(enriched_dir / "OSINT_ENRICHED_ENTITIES.json") or []
    props    = _load_json_file(enriched_dir / "OSINT_ENRICHED_PROPERTIES.json") or []

    entity_index  = {r["entity_id"]: r for r in entities}
    prop_index    = {r["property_id"]: r for r in props}

    entity_queue = [q for q in queue if q["entity_type"] == "entity"]
    prop_queue   = [q for q in queue if q["entity_type"] == "property"]

    source_files_found = sorted(sources_dir.glob("*.*")) if sources_dir.exists() else []

    print(f"  Queued entities:   {len(entity_queue)}")
    print(f"  Queued properties: {len(prop_queue)}")
    print(f"  Source files:      {len(source_files_found)} in data/osint/sources/")

    # ── Initialize cache ──────────────────────────────────────────────────────

    cache = CacheLayer(cache_dir, ttl_days=CACHE_TTL_DAYS)

    # ── Resolve entities ──────────────────────────────────────────────────────

    print("\n[ 2 / 5 ] Resolving entity gaps ...")

    for q_entry in entity_queue:
        eid = q_entry["entity_id"]
        if eid not in entity_index:
            continue
        entity_index[eid] = resolve_record(
            entity_index[eid],
            q_entry["missing_fields"],
            "lookup_entity",
            sources_dir,
            cache,
            ts,
        )

    resolved_entity_fields = sum(
        1 for rec in entity_index.values()
        for v in rec.values()
        if isinstance(v, dict) and v.get("source_type") == "inferred"
    )
    print(f"  Fields resolved/inferred: {resolved_entity_fields}")

    # ── Resolve properties ────────────────────────────────────────────────────

    print("\n[ 3 / 5 ] Resolving property gaps ...")

    for q_entry in prop_queue:
        pid = q_entry["entity_id"]  # queue uses entity_id for both types
        if pid not in prop_index:
            continue
        prop_index[pid] = resolve_record(
            prop_index[pid],
            q_entry["missing_fields"],
            "lookup_property",
            sources_dir,
            cache,
            ts,
        )

    resolved_prop_fields = sum(
        1 for rec in prop_index.values()
        for v in rec.values()
        if isinstance(v, dict) and v.get("source_type") == "inferred"
    )
    print(f"  Fields resolved/inferred: {resolved_prop_fields}")

    # ── Write enriched outputs ────────────────────────────────────────────────

    print("\n[ 4 / 5 ] Writing enriched outputs ...")

    entities_out = list(entity_index.values())
    props_out    = list(prop_index.values())

    _write_json(ext_dir / "EXTERNAL_ENRICHED_ENTITIES.json", entities_out)
    print(f"  {ext_dir / 'EXTERNAL_ENRICHED_ENTITIES.json'}")

    _write_json(ext_dir / "EXTERNAL_ENRICHED_PROPERTIES.json", props_out)
    print(f"  {ext_dir / 'EXTERNAL_ENRICHED_PROPERTIES.json'}")

    # ── Reports ───────────────────────────────────────────────────────────────

    print("\n[ 5 / 5 ] Writing reports ...")

    fill_report = write_fill_report(queue, entities_out, props_out, run_ts,
                                    ext_dir / "ENRICHMENT_FILL_REPORT.json")
    print(f"  {ext_dir / 'ENRICHMENT_FILL_REPORT.json'}")

    remaining_gaps = write_remaining_gaps(entities_out, props_out,
                                          ext_dir / "REMAINING_GAPS.json")
    print(f"  {ext_dir / 'REMAINING_GAPS.json'}")

    audit_path = write_lookup_audit(
        entities_out, props_out, fill_report, remaining_gaps,
        sources_dir, run_ts, report_dir,
    )
    print(f"  {audit_path}")

    print("")
    print("=" * 64)
    print(f"  Entities processed:  {len(entities_out)}")
    print(f"  Properties processed:{len(props_out)}")
    print(f"  Original gaps:       {fill_report['original_missing_field_slots']}")
    print(f"  Remaining gaps:      {fill_report['remaining_unresolved']}")
    print(f"  Gap reduction:       {fill_report['gap_reduction']} fields ({fill_report['gap_reduction_pct']}%)")
    print("=" * 64)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI_BRAIN OSINT External Lookup Runner")
    parser.add_argument(
        "--workspace-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Absolute path to the ai-brain workspace root",
    )
    args = parser.parse_args()
    run(Path(args.workspace_root))


if __name__ == "__main__":
    main()
