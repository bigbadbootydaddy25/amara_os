"""
Analyzes a collection of OwnerRecords to build BuyerProfiles and classify each
as a verified builder, possible cash buyer, or quarantined (insufficient evidence).
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Tuple

from models import BuyerProfile, OwnerRecord, QuarantinedRecord
from signals import (
    detect_profile_signals,
    detect_record_signals,
)

# ---------------------------------------------------------------------------
# Validation / quarantine
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = ("parcel_id", "owner_name")

_NOISE_NAMES = {
    "", "UNKNOWN", "N/A", "NA", "NONE", "NULL", "INDIVIDUAL", "OWNER",
}


def validate_record(record: OwnerRecord) -> Tuple[bool, str]:
    """Returns (is_valid, reason). Reason is empty string when valid."""
    for f in _REQUIRED_FIELDS:
        if not getattr(record, f, "").strip():
            return False, f"Missing required field: {f}"
    if record.owner_name in _NOISE_NAMES:
        return False, f"Non-informative owner name: '{record.owner_name}'"
    return True, ""


# ---------------------------------------------------------------------------
# Record grouping
# ---------------------------------------------------------------------------

def group_records_by_owner(
    records: List[OwnerRecord],
) -> Tuple[Dict[str, BuyerProfile], List[QuarantinedRecord]]:
    """
    Groups valid records by normalized owner name into BuyerProfiles.
    Invalid records are collected in the quarantine list.
    """
    profiles: Dict[str, BuyerProfile] = {}
    quarantine: List[QuarantinedRecord] = []

    for record in records:
        valid, reason = validate_record(record)
        if not valid:
            quarantine.append(QuarantinedRecord(
                parcel_id=record.parcel_id,
                owner_name=record.owner_name,
                reason=reason,
                raw=record.raw,
            ))
            continue

        key = _normalize_owner_key(record.owner_name)
        if key not in profiles:
            profiles[key] = BuyerProfile(owner_name=record.owner_name)

        profile = profiles[key]
        if record.parcel_id not in profile.parcel_ids:
            profile.parcel_ids.append(record.parcel_id)
            profile.records.append(record)

        # Run record-level signals immediately
        for sig in detect_record_signals(record):
            if sig.signal_type not in [s.signal_type for s in profile.signals]:
                profile.signals.append(sig)

    return profiles, quarantine


# ---------------------------------------------------------------------------
# Profile-level signal enrichment
# ---------------------------------------------------------------------------

def enrich_profiles(profiles: Dict[str, BuyerProfile]) -> None:
    """Adds cross-record signals to every profile (in-place)."""
    for profile in profiles.values():
        for sig in detect_profile_signals(profile):
            # Avoid duplicating signal types already present
            existing_types = {s.signal_type for s in profile.signals}
            if sig.signal_type not in existing_types:
                profile.signals.append(sig)


# ---------------------------------------------------------------------------
# Builder detector
# ---------------------------------------------------------------------------

_BUILDER_SIGNAL_TYPES = {
    "LLC_COMPANY",
    "BUILDER_KEYWORD",
    "VACANT_LAND",
    "PERMIT_ACTIVITY",
    "MULTIPLE_NEARBY_PARCELS",
    "VACANT_LAND_CONCENTRATION",
    "INFILL_ACTIVITY",
    "REPEAT_ACQUISITIONS",
    "RECENT_PURCHASE_CLUSTERING",
}

_BUILDER_SCORE_THRESHOLD = 40


def classify_builders(
    profiles: Dict[str, BuyerProfile],
) -> List[BuyerProfile]:
    """Returns profiles that score as verified builders."""
    return [
        p for p in profiles.values()
        if not p.is_quarantined and p.builder_score >= _BUILDER_SCORE_THRESHOLD
    ]


# ---------------------------------------------------------------------------
# Cash buyer / investor detector
# ---------------------------------------------------------------------------

_INVESTOR_SIGNAL_TYPES = {
    "LLC_COMPANY",
    "INVESTOR_KEYWORD",
    "MAILING_MISMATCH",
    "REPEAT_ACQUISITIONS",
    "MULTIPLE_NEARBY_PARCELS",
    "RECENT_PURCHASE_CLUSTERING",
    "ROUND_SALE_PRICE",
}

_INVESTOR_SCORE_THRESHOLD = 30


def classify_cash_buyers(
    profiles: Dict[str, BuyerProfile],
) -> List[BuyerProfile]:
    """Returns profiles that score as possible cash buyers / investors."""
    return [
        p for p in profiles.values()
        if not p.is_quarantined and p.investor_score >= _INVESTOR_SCORE_THRESHOLD
    ]


# ---------------------------------------------------------------------------
# Quarantine weak profiles
# ---------------------------------------------------------------------------

_MIN_SIGNALS_REQUIRED = 2


def quarantine_weak_profiles(
    profiles: Dict[str, BuyerProfile],
) -> None:
    """
    Marks profiles with too few signals as quarantined (in-place).
    These are preserved but excluded from primary outputs.
    """
    for profile in profiles.values():
        if profile.is_quarantined:
            continue
        if len(profile.signals) < _MIN_SIGNALS_REQUIRED:
            profile.is_quarantined = True
            profile.quarantine_reason = (
                f"Only {len(profile.signals)} signal(s) detected — "
                "insufficient evidence for classification"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_owner_key(name: str) -> str:
    """Strips punctuation/extra whitespace for grouping purposes."""
    cleaned = re.sub(r"[.,'\-]", " ", name)
    return re.sub(r"\s+", " ", cleaned).strip()
