"""
Signal detection: identifies all buyer/builder signals from an OwnerRecord.
Each signal has a type, the triggering value, a score weight, and evidence text.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import List

from models import BuyerProfile, DetectedSignal, OwnerRecord

# ---------------------------------------------------------------------------
# Keyword registries
# ---------------------------------------------------------------------------

BUILDER_KEYWORDS = {
    "CONSTRUCTION", "CONSTRUCTORS", "BUILDER", "BUILDERS", "BUILDING",
    "DEVELOPMENT", "DEVELOPMENTS", "DEVELOPER", "DEVELOPERS",
    "HOMES", "HOME BUILDERS", "HOMEBUILDER", "HOUSING",
    "REALTY", "REAL ESTATE",
    "CONTRACTORS", "CONTRACTOR",
    "INFILL", "CUSTOM HOMES", "SPEC",
    "RESIDENTIAL", "COMMUNITIES", "COMMUNITY",
    "LAND DEVELOPMENT", "LAND DEV",
}

ENTITY_SUFFIXES = {
    "LLC", "L.L.C", "L.L.C.", "LP", "L.P.", "LLP",
    "INC", "INC.", "CORP", "CORP.", "CO", "CO.",
    "LTD", "LTD.", "COMPANY", "COMPANIES",
    "TRUST", "TRUSTEES", "TRUSTEE",
    "GROUP", "HOLDINGS", "VENTURES", "ENTERPRISES",
    "ASSOCIATES", "PARTNERS", "PARTNERSHIP",
    "FUND", "CAPITAL", "ACQUISITIONS", "INVESTMENTS",
    "PROPERTIES", "PROPERTY", "ASSETS",
}

INVESTOR_KEYWORDS = {
    "INVESTMENT", "INVESTMENTS", "INVESTORS", "INVESTOR",
    "CAPITAL", "FUND", "ACQUISITION", "ACQUISITIONS",
    "HOLDINGS", "VENTURES", "ASSETS", "PORTFOLIO",
    "RENTALS", "RENTAL", "LEASING",
}

VACANT_LAND_USES = {
    "VACANT", "UNIMPROVED", "RAW LAND", "LAND", "LOT",
    "UNDEVELOPED", "BARE LAND", "EMPTY LOT",
}

# ---------------------------------------------------------------------------
# Individual signal detectors (operate on a single record)
# ---------------------------------------------------------------------------

def detect_llc_company(record: OwnerRecord) -> List[DetectedSignal]:
    name = record.owner_name
    signals: List[DetectedSignal] = []
    for suffix in ENTITY_SUFFIXES:
        pattern = r"\b" + re.escape(suffix) + r"\.?\b"
        if re.search(pattern, name):
            signals.append(DetectedSignal(
                signal_type="LLC_COMPANY",
                value=suffix,
                weight=15,
                evidence=f"Owner name '{name}' contains entity suffix '{suffix}'",
            ))
            break  # one LLC signal per record is enough
    return signals


def detect_builder_keywords(record: OwnerRecord) -> List[DetectedSignal]:
    name = record.owner_name
    signals: List[DetectedSignal] = []
    for kw in BUILDER_KEYWORDS:
        if kw in name:
            signals.append(DetectedSignal(
                signal_type="BUILDER_KEYWORD",
                value=kw,
                weight=20,
                evidence=f"Owner name '{name}' contains builder keyword '{kw}'",
            ))
    return signals


def detect_investor_keywords(record: OwnerRecord) -> List[DetectedSignal]:
    name = record.owner_name
    signals: List[DetectedSignal] = []
    for kw in INVESTOR_KEYWORDS:
        if kw in name:
            signals.append(DetectedSignal(
                signal_type="INVESTOR_KEYWORD",
                value=kw,
                weight=10,
                evidence=f"Owner name '{name}' contains investor keyword '{kw}'",
            ))
    return signals


def detect_vacant_land(record: OwnerRecord) -> List[DetectedSignal]:
    signals: List[DetectedSignal] = []
    if record.is_vacant:
        signals.append(DetectedSignal(
            signal_type="VACANT_LAND",
            value="is_vacant=True",
            weight=15,
            evidence=f"Parcel {record.parcel_id} flagged as vacant",
        ))
        return signals
    for lu in VACANT_LAND_USES:
        if lu in record.land_use:
            signals.append(DetectedSignal(
                signal_type="VACANT_LAND",
                value=record.land_use,
                weight=15,
                evidence=f"Land use '{record.land_use}' indicates vacant/unimproved parcel",
            ))
            break
    return signals


def detect_permit_activity(record: OwnerRecord) -> List[DetectedSignal]:
    if record.permit_count > 0:
        return [DetectedSignal(
            signal_type="PERMIT_ACTIVITY",
            value=str(record.permit_count),
            weight=25,
            evidence=f"Parcel {record.parcel_id} has {record.permit_count} permit(s) on file",
        )]
    return []


def detect_mailing_mismatch(record: OwnerRecord) -> List[DetectedSignal]:
    """Flags when mailing address differs from property address."""
    if not record.mailing_address or not record.property_address:
        return []
    norm_mail = _normalize_address(record.mailing_address)
    norm_prop = _normalize_address(record.property_address)
    if norm_mail and norm_prop and norm_mail != norm_prop:
        return [DetectedSignal(
            signal_type="MAILING_MISMATCH",
            value=record.mailing_address,
            weight=20,
            evidence=(
                f"Mailing '{record.mailing_address}' differs from "
                f"property address '{record.property_address}'"
            ),
        )]
    return []


def detect_round_price(record: OwnerRecord) -> List[DetectedSignal]:
    """Round-number sale price is a proxy for all-cash transaction."""
    price = record.sale_price
    if price >= 10_000 and price % 5000 == 0:
        return [DetectedSignal(
            signal_type="ROUND_SALE_PRICE",
            value=str(price),
            weight=5,
            evidence=f"Sale price ${price:,.0f} is a round number (cash indicator)",
        )]
    return []


# ---------------------------------------------------------------------------
# Cross-record signals (operate on a BuyerProfile)
# ---------------------------------------------------------------------------

def detect_repeat_acquisitions(profile: BuyerProfile) -> List[DetectedSignal]:
    count = profile.parcel_count
    if count >= 5:
        weight = 25
    elif count >= 3:
        weight = 15
    else:
        return []
    return [DetectedSignal(
        signal_type="REPEAT_ACQUISITIONS",
        value=str(count),
        weight=weight,
        evidence=f"Owner '{profile.owner_name}' acquired {count} parcels",
    )]


def detect_multiple_nearby_parcels(profile: BuyerProfile) -> List[DetectedSignal]:
    """Detects same owner holding 2+ parcels in the same ZIP."""
    from collections import Counter
    zip_counts = Counter(r.zip_code for r in profile.records if r.zip_code)
    signals: List[DetectedSignal] = []
    for zip_code, count in zip_counts.items():
        if count >= 2:
            signals.append(DetectedSignal(
                signal_type="MULTIPLE_NEARBY_PARCELS",
                value=zip_code,
                weight=20,
                evidence=(
                    f"Owner '{profile.owner_name}' holds {count} parcels "
                    f"in ZIP {zip_code}"
                ),
            ))
    return signals


def detect_recent_purchase_clustering(
    profile: BuyerProfile,
    window_days: int = 90,
) -> List[DetectedSignal]:
    """Flags if 2+ purchases fall within any rolling window_days window."""
    dates = _parse_dates(profile.acquisition_dates)
    if len(dates) < 2:
        return []
    dates.sort()
    window = timedelta(days=window_days)
    for i, d in enumerate(dates):
        cluster = [x for x in dates if d <= x <= d + window]
        if len(cluster) >= 2:
            return [DetectedSignal(
                signal_type="RECENT_PURCHASE_CLUSTERING",
                value=f"{len(cluster)} purchases within {window_days} days",
                weight=10,
                evidence=(
                    f"Owner '{profile.owner_name}' made {len(cluster)} purchases "
                    f"within a {window_days}-day window starting {d}"
                ),
            )]
    return []


def detect_vacant_land_concentration(profile: BuyerProfile) -> List[DetectedSignal]:
    """Flags owners with 2+ vacant parcels — strong builder/developer signal."""
    vacant = [r for r in profile.records if _is_vacant(r)]
    if len(vacant) >= 2:
        return [DetectedSignal(
            signal_type="VACANT_LAND_CONCENTRATION",
            value=str(len(vacant)),
            weight=20,
            evidence=(
                f"Owner '{profile.owner_name}' owns {len(vacant)} vacant/unimproved parcels"
            ),
        )]
    return []


def detect_infill_activity(profile: BuyerProfile) -> List[DetectedSignal]:
    """Vacant parcel + permits = infill development signal."""
    infill = [r for r in profile.records if _is_vacant(r) and r.permit_count > 0]
    if infill:
        total_permits = sum(r.permit_count for r in infill)
        return [DetectedSignal(
            signal_type="INFILL_ACTIVITY",
            value=f"{len(infill)} parcels / {total_permits} permits",
            weight=25,
            evidence=(
                f"Owner '{profile.owner_name}' has permits on {len(infill)} "
                f"vacant parcel(s) — indicates infill development"
            ),
        )]
    return []


# ---------------------------------------------------------------------------
# Aggregate: run all record-level detectors for one record
# ---------------------------------------------------------------------------

def detect_record_signals(record: OwnerRecord) -> List[DetectedSignal]:
    signals: List[DetectedSignal] = []
    signals += detect_llc_company(record)
    signals += detect_builder_keywords(record)
    signals += detect_investor_keywords(record)
    signals += detect_vacant_land(record)
    signals += detect_permit_activity(record)
    signals += detect_mailing_mismatch(record)
    signals += detect_round_price(record)
    return signals


# Aggregate: run all profile-level detectors after grouping
def detect_profile_signals(profile: BuyerProfile) -> List[DetectedSignal]:
    signals: List[DetectedSignal] = []
    signals += detect_repeat_acquisitions(profile)
    signals += detect_multiple_nearby_parcels(profile)
    signals += detect_recent_purchase_clustering(profile)
    signals += detect_vacant_land_concentration(profile)
    signals += detect_infill_activity(profile)
    return signals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_address(addr: str) -> str:
    return re.sub(r"\s+", " ", addr.upper().strip())


def _is_vacant(record: OwnerRecord) -> bool:
    if record.is_vacant:
        return True
    for lu in VACANT_LAND_USES:
        if lu in record.land_use:
            return True
    return False


def _parse_dates(date_strings: List[str]) -> List[date]:
    parsed: List[date] = []
    for ds in date_strings:
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%m-%d-%Y"):
            try:
                parsed.append(datetime.strptime(ds, fmt).date())
                break
            except (ValueError, TypeError):
                continue
    return parsed
