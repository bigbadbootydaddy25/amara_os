"""
Normalization and deduplication layer for scraped listings.

Converts RawListing → NormalizedListing with clean types,
fills missing fields with safe defaults, and deduplicates by address.
"""

import hashlib
import re
from dataclasses import dataclass
from workers.remote.scraper import RawListing


@dataclass
class NormalizedListing:
    address: str
    price: int
    beds: int
    baths: float
    sqft: int
    dom: int
    keywords: list[str]
    source: str
    url: str
    zip_code: str
    listing_id: str        # SHA256 of address — dedup key
    has_distress: bool     # True if any keyword matched
    distress_score: float  # 0.0–1.0 based on keyword count + DOM


_HIGH_VALUE_KEYWORDS = {
    "probate", "estate sale", "inherited", "foreclosure",
    "pre-foreclosure", "preforeclosure", "short sale", "motivated seller",
}


def _make_id(address: str) -> str:
    return hashlib.sha256(address.strip().lower().encode()).hexdigest()[:16]


def _clean_address(raw: str) -> str:
    # Remove extra whitespace and newlines
    return " ".join(raw.split())


def _distress_score(keywords: list[str], dom: int) -> float:
    """
    Score 0.0–1.0:
    - Each keyword: +0.10 (high-value keywords: +0.20)
    - DOM 90–119: +0.10
    - DOM 120–179: +0.20
    - DOM 180+:   +0.30
    """
    score = 0.0
    for kw in keywords:
        score += 0.20 if kw in _HIGH_VALUE_KEYWORDS else 0.10

    if dom >= 180:
        score += 0.30
    elif dom >= 120:
        score += 0.20
    elif dom >= 90:
        score += 0.10

    return min(round(score, 2), 1.0)


def normalize(raw: RawListing) -> NormalizedListing | None:
    """
    Normalize a single RawListing. Returns None if the listing is invalid
    (missing address or zero price).
    """
    address = _clean_address(raw.address)
    if not address or raw.price <= 0:
        return None

    keywords = list(dict.fromkeys(kw.lower() for kw in raw.keywords))  # dedup keywords

    return NormalizedListing(
        address=address,
        price=max(0, raw.price),
        beds=max(0, raw.beds),
        baths=max(0.0, raw.baths),
        sqft=max(0, raw.sqft),
        dom=max(0, raw.dom),
        keywords=keywords,
        source=raw.source,
        url=raw.url or "",
        zip_code=raw.zip_code,
        listing_id=_make_id(address),
        has_distress=len(keywords) > 0,
        distress_score=_distress_score(keywords, raw.dom),
    )


def normalize_batch(
    raws: list[RawListing],
    dedup: bool = True,
) -> list[NormalizedListing]:
    """
    Normalize a list of RawListings.
    - Drops invalid entries
    - Deduplicates by listing_id (address hash) when dedup=True
    - Sorts by distress_score desc, then DOM desc
    """
    seen: set[str] = set()
    results: list[NormalizedListing] = []

    for raw in raws:
        listing = normalize(raw)
        if listing is None:
            continue
        if dedup and listing.listing_id in seen:
            continue
        seen.add(listing.listing_id)
        results.append(listing)

    results.sort(key=lambda x: (x.distress_score, x.dom), reverse=True)
    return results


def filter_distressed(
    listings: list[NormalizedListing],
    require_keywords: bool = True,
    min_dom: int = 90,
    min_distress_score: float = 0.0,
) -> list[NormalizedListing]:
    """
    Filter to distressed listings only.
    """
    return [
        l for l in listings
        if l.dom >= min_dom
        and (not require_keywords or l.has_distress)
        and l.distress_score >= min_distress_score
    ]
