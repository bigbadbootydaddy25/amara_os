"""
Data models for the Parcel Match Agent.

Parcels are opportunity records to be matched.
LoadedBuyerProfile is a lightweight view of builder-verification outputs.
MatchSignal / ParcelMatch / ParcelOpportunity carry match results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Parcel (opportunity record)
# ---------------------------------------------------------------------------

@dataclass
class Parcel:
    parcel_id: str
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    land_use: str = ""
    acres: float = 0.0
    zoning: str = ""
    is_vacant: bool = False
    owner_name: str = ""
    sale_price: float = 0.0
    sale_date: str = ""
    asking_price: float = 0.0
    arv: float = 0.0              # after-repair/after-build value
    permit_count: int = 0
    days_on_market: int = 0
    distressed: bool = False
    notes: str = ""
    source_file: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def effective_price(self) -> float:
        """Best available price signal for match scoring."""
        return self.asking_price if self.asking_price > 0 else self.sale_price

    @classmethod
    def from_dict(cls, d: Dict[str, Any], source_file: str = "") -> "Parcel":
        return cls(
            parcel_id=str(d.get("parcel_id", "")).strip(),
            address=str(d.get("address", d.get("property_address", ""))).strip().upper(),
            city=str(d.get("city", "")).strip().upper(),
            state=str(d.get("state", "")).strip().upper(),
            zip_code=str(d.get("zip_code", d.get("zip", ""))).strip(),
            lat=_safe_float(d.get("lat")),
            lon=_safe_float(d.get("lon")),
            land_use=str(d.get("land_use", "")).strip().upper(),
            acres=float(d.get("acres", 0) or 0),
            zoning=str(d.get("zoning", "")).strip().upper(),
            is_vacant=bool(d.get("is_vacant", False)),
            owner_name=str(d.get("owner_name", "")).strip().upper(),
            sale_price=float(d.get("sale_price", 0) or 0),
            sale_date=str(d.get("sale_date", "")).strip(),
            asking_price=float(d.get("asking_price", 0) or 0),
            arv=float(d.get("arv", 0) or 0),
            permit_count=int(d.get("permit_count", 0) or 0),
            days_on_market=int(d.get("days_on_market", 0) or 0),
            distressed=bool(d.get("distressed", False)),
            notes=str(d.get("notes", "")).strip(),
            source_file=source_file,
            raw=d,
        )


# ---------------------------------------------------------------------------
# Buyer profile (loaded from builder-verification JSON output)
# ---------------------------------------------------------------------------

@dataclass
class LoadedBuyerProfile:
    owner_name: str
    parcel_count: int = 0
    zip_codes: List[str] = field(default_factory=list)
    acquisition_dates: List[str] = field(default_factory=list)
    total_spend: float = 0.0
    builder_score: int = 0
    investor_score: int = 0
    is_verified_builder: bool = False
    is_possible_cash_buyer: bool = False
    is_quarantined: bool = False
    signal_types: List[str] = field(default_factory=list)

    @property
    def avg_price(self) -> float:
        if self.parcel_count > 0 and self.total_spend > 0:
            return self.total_spend / self.parcel_count
        return 0.0

    @property
    def price_range(self) -> tuple:
        """±40% band around average acquisition price."""
        avg = self.avg_price
        if avg <= 0:
            return (0.0, 0.0)
        return (avg * 0.60, avg * 1.40)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LoadedBuyerProfile":
        signal_types = [
            s.get("type", s.get("signal_type", ""))
            for s in d.get("signal_evidence", [])
        ]
        return cls(
            owner_name=str(d.get("owner_name", "")).strip(),
            parcel_count=int(d.get("parcel_count", 0) or 0),
            zip_codes=[str(z) for z in d.get("zip_codes", [])],
            acquisition_dates=d.get("acquisition_dates", []),
            total_spend=float(d.get("total_spend", 0) or 0),
            builder_score=int(d.get("builder_score", 0) or 0),
            investor_score=int(d.get("investor_score", 0) or 0),
            is_verified_builder=bool(d.get("is_verified_builder", False)),
            is_possible_cash_buyer=bool(d.get("is_possible_cash_buyer", False)),
            is_quarantined=bool(d.get("is_quarantined", False)),
            signal_types=signal_types,
        )


# ---------------------------------------------------------------------------
# Match signal (atomic evidence unit for a parcel↔buyer match)
# ---------------------------------------------------------------------------

@dataclass
class MatchSignal:
    signal_type: str
    value: str
    weight: int
    evidence: str


# ---------------------------------------------------------------------------
# ParcelMatch (one parcel matched to one buyer/builder)
# ---------------------------------------------------------------------------

@dataclass
class ParcelMatch:
    parcel_id: str
    buyer_name: str
    match_score: int          # 0–100
    match_type: str           # "BUILDER" | "INVESTOR" | "CASH_BUYER"
    signals: List[MatchSignal] = field(default_factory=list)
    disposition_path: str = ""
    summary: str = ""

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


# ---------------------------------------------------------------------------
# DispositionPath (likely outcome for a parcel)
# ---------------------------------------------------------------------------

@dataclass
class DispositionPath:
    path_type: str        # INFILL_BUILD | WHOLESALE_TO_INVESTOR | RETAIL_LISTING |
                          # HOLD_FOR_DEVELOPMENT | REHAB_FLIP
    confidence: int       # 0–100
    evidence: List[str] = field(default_factory=list)
    recommended_buyers: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ParcelOpportunity (aggregated results for one parcel)
# ---------------------------------------------------------------------------

@dataclass
class ParcelOpportunity:
    parcel: Parcel
    top_buyer_matches: List[ParcelMatch] = field(default_factory=list)
    top_builder_matches: List[ParcelMatch] = field(default_factory=list)
    disposition_paths: List[DispositionPath] = field(default_factory=list)
    summary: str = ""

    @property
    def best_match_score(self) -> int:
        all_matches = self.top_buyer_matches + self.top_builder_matches
        return max((m.match_score for m in all_matches), default=0)

    @property
    def primary_disposition(self) -> Optional[DispositionPath]:
        if self.disposition_paths:
            return max(self.disposition_paths, key=lambda p: p.confidence)
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val: Any) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None
