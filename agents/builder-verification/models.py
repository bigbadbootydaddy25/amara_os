"""
Data models for the Builder Verification Agent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class OwnerRecord:
    parcel_id: str
    owner_name: str
    mailing_address: str = ""
    property_address: str = ""
    sale_date: str = ""       # YYYY-MM-DD or MM/DD/YYYY
    sale_price: float = 0.0
    land_use: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    permit_count: int = 0
    is_vacant: bool = False
    source_file: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any], source_file: str = "") -> "OwnerRecord":
        return cls(
            parcel_id=str(d.get("parcel_id", "")).strip(),
            owner_name=str(d.get("owner_name", "")).strip().upper(),
            mailing_address=str(d.get("mailing_address", "")).strip().upper(),
            property_address=str(d.get("property_address", "")).strip().upper(),
            sale_date=str(d.get("sale_date", "")).strip(),
            sale_price=float(d.get("sale_price", 0) or 0),
            land_use=str(d.get("land_use", "")).strip().upper(),
            city=str(d.get("city", "")).strip().upper(),
            state=str(d.get("state", "")).strip().upper(),
            zip_code=str(d.get("zip_code", d.get("zip", ""))).strip(),
            lat=_safe_float(d.get("lat")),
            lon=_safe_float(d.get("lon")),
            permit_count=int(d.get("permit_count", 0) or 0),
            is_vacant=bool(d.get("is_vacant", False)),
            source_file=source_file,
            raw=d,
        )


@dataclass
class DetectedSignal:
    signal_type: str    # e.g. "LLC_COMPANY", "BUILDER_KEYWORD"
    value: str          # specific value that triggered it
    weight: int         # contribution to score
    evidence: str       # human-readable description


@dataclass
class BuyerProfile:
    owner_name: str
    parcel_ids: List[str] = field(default_factory=list)
    records: List[OwnerRecord] = field(default_factory=list)
    signals: List[DetectedSignal] = field(default_factory=list)
    builder_score: int = 0
    investor_score: int = 0
    is_verified_builder: bool = False
    is_possible_cash_buyer: bool = False
    is_quarantined: bool = False
    quarantine_reason: str = ""
    summary: str = ""

    @property
    def parcel_count(self) -> int:
        return len(self.parcel_ids)

    @property
    def zip_codes(self) -> List[str]:
        return sorted({r.zip_code for r in self.records if r.zip_code})

    @property
    def acquisition_dates(self) -> List[str]:
        return sorted([r.sale_date for r in self.records if r.sale_date])

    @property
    def total_spend(self) -> float:
        return sum(r.sale_price for r in self.records)

    @property
    def signal_types(self) -> List[str]:
        return [s.signal_type for s in self.signals]

    def signal_evidence(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": s.signal_type,
                "value": s.value,
                "weight": s.weight,
                "evidence": s.evidence,
            }
            for s in self.signals
        ]


@dataclass
class QuarantinedRecord:
    parcel_id: str
    owner_name: str
    reason: str
    raw: Dict[str, Any] = field(default_factory=dict)


def _safe_float(val: Any) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None
