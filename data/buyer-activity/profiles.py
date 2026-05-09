"""
Build BuyerActivityProfile objects from ingested Transaction lists.

Profiles are always created from buyer/grantee/owner fields present in the CSV.
A seed match enriches a profile with the buyer's known ID and status but is
never required — profiles without a seed match are still emitted.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from ingest import Transaction          # noqa: E402
from seeds import BuyerSeed, match_seed  # noqa: E402


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class BuyerActivityProfile:
    buyer_key: str                    # normalised grouping key (alphanum only)
    display_name: str                 # best human-readable label
    entity_name:     Optional[str]
    individual_name: Optional[str]
    seed_id:     Optional[str]        # BUY-XXXX if matched to a known seed
    seed_status: Optional[str]
    transaction_count: int
    zip_codes:       list[str]
    property_types:  list[str]
    financing_types: list[str]
    price_min: Optional[float]
    price_max: Optional[float]
    price_avg: Optional[float]
    most_recent_sale: Optional[str]
    earliest_sale:    Optional[str]
    source_files:    list[str]        # which CSVs contributed records


# ── Public API ────────────────────────────────────────────────────────────────

def build_profiles(
    transactions: list[Transaction],
    seeds: list[BuyerSeed],
) -> list[BuyerActivityProfile]:
    """
    Group transactions by buyer key and build one profile per unique buyer.

    Profiles are created for every buyer present in the CSVs, regardless of
    whether they match an entity seed.
    """
    grouped: dict[str, list[Transaction]] = {}
    for txn in transactions:
        key = _buyer_key(txn)
        if key:
            grouped.setdefault(key, []).append(txn)

    profiles = [_make_profile(key, txns, seeds) for key, txns in grouped.items()]
    profiles.sort(key=lambda p: p.transaction_count, reverse=True)
    return profiles


# ── Profile construction ──────────────────────────────────────────────────────

def _make_profile(
    key: str,
    txns: list[Transaction],
    seeds: list[BuyerSeed],
) -> BuyerActivityProfile:
    entity_names     = [t.buyer_entity for t in txns if t.buyer_entity]
    individual_names = [t.buyer_name   for t in txns if t.buyer_name]

    entity_name     = _most_common(entity_names)
    individual_name = _most_common(individual_names)
    display_name    = entity_name or individual_name or key

    seed = match_seed(entity_name, individual_name, seeds)

    prices = [t.sale_price for t in txns if t.sale_price is not None]
    dates  = sorted(d for t in txns if (d := t.sale_date))

    return BuyerActivityProfile(
        buyer_key=key,
        display_name=display_name,
        entity_name=entity_name,
        individual_name=individual_name,
        seed_id=seed.buyer_id if seed else None,
        seed_status=seed.status if seed else None,
        transaction_count=len(txns),
        zip_codes=_unique_sorted(t.zip for t in txns if t.zip),
        property_types=_unique_sorted(t.property_type for t in txns if t.property_type),
        financing_types=_unique_sorted(t.financing_type for t in txns if t.financing_type),
        price_min=min(prices) if prices else None,
        price_max=max(prices) if prices else None,
        price_avg=sum(prices) / len(prices) if prices else None,
        most_recent_sale=dates[-1] if dates else None,
        earliest_sale=dates[0] if dates else None,
        source_files=_unique_sorted(t.source_file for t in txns),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _buyer_key(txn: Transaction) -> Optional[str]:
    raw = txn.buyer_entity or txn.buyer_name or ""
    return re.sub(r"[^a-z0-9]", "", raw.lower()) or None


def _most_common(items: list[str]) -> Optional[str]:
    if not items:
        return None
    return max(set(items), key=items.count)


def _unique_sorted(it) -> list[str]:
    return sorted(set(it))
