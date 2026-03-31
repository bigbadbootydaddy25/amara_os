"""
AMARA OS — Buyer Discovery Engine

Scores buyers from transaction history, infers buy boxes from patterns,
ranks buyers by activity and reliability, and identifies new buyers from
PropStream exports.

Core principle: buyer-first. Every buyer discovered must be qualified
before entering the vault (2+ cash transactions minimum).
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from system.config import (
    ACTIVITY_HOT, ACTIVITY_WARM, ACTIVITY_COLD, ACTIVITY_UNKNOWN,
    BUYER_STATUS_ACTIVE, BUYER_STATUS_PAUSED, BUYER_STATUS_INACTIVE,
    VAULT_BUYERS,
)
from system.vault import list_vault, read_vault_file, write_vault_file, next_id


# ─── Buyer Transaction (lightweight record) ───────────────────────────────────

@dataclass
class BuyerTransaction:
    address:        str
    zip_code:       str
    purchase_date:  date | None
    purchase_price: float
    property_type:  str     = "SFR"
    beds:           float   = 0
    sqft:           int     = 0
    is_cash:        bool    = True
    days_to_close:  int     = 0


# ─── Buyer Score Output ───────────────────────────────────────────────────────

@dataclass
class BuyerScore:
    buyer_id:           str
    buyer_name:         str

    # Scoring components (all 0.0–1.0)
    activity_score:     float = 0.0     # recency + volume of recent purchases
    reliability_score:  float = 0.0     # closes what they commit to (proxy: deal count consistency)
    speed_score:        float = 0.0     # avg days-to-close (lower = better)
    zip_concentration:  float = 0.0     # focused buyer vs. scattered
    composite_score:    float = 0.0     # weighted composite

    # Activity
    total_txns:         int   = 0
    txns_12mo:          int   = 0
    txns_24mo:          int   = 0
    active_zips:        list[str] = field(default_factory=list)
    avg_purchase_price: float = 0.0
    avg_days_to_close:  float = 0.0

    # Activity level
    activity_level:     str   = ACTIVITY_UNKNOWN   # hot / warm / cold / unknown

    def summary(self) -> str:
        return (
            f"[{self.activity_level.upper()}] {self.buyer_id} — {self.buyer_name}\n"
            f"  Composite: {self.composite_score:.2f} | "
            f"Activity: {self.activity_score:.2f} | "
            f"Reliability: {self.reliability_score:.2f} | "
            f"Speed: {self.speed_score:.2f}\n"
            f"  Txns: {self.txns_12mo}/12mo · {self.txns_24mo}/24mo · {self.total_txns} total\n"
            f"  Avg Price: ${self.avg_purchase_price:,.0f} | "
            f"Avg Close: {self.avg_days_to_close:.0f}d | "
            f"ZIPs: {', '.join(self.active_zips[:5])}"
        )


# ─── Inferred Buy Box ─────────────────────────────────────────────────────────

@dataclass
class InferredBuyBox:
    buyer_id:             str
    zip_codes:            list[str]
    asset_types:          list[str]
    min_price:            float
    max_price:            float
    avg_price:            float
    price_band_width:     float
    min_beds:             float
    max_beds:             float
    min_sqft:             int
    max_sqft:             int
    confidence:           float       # 0.0–1.0 — how reliable is this inference
    inferred_from_n:      int         # number of transactions used
    notes:                list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Buy Box [{self.buyer_id}] — confidence {self.confidence:.2f} (n={self.inferred_from_n})\n"
            f"  ZIPs: {', '.join(self.zip_codes)}\n"
            f"  Price: ${self.min_price:,.0f} – ${self.max_price:,.0f} (avg ${self.avg_price:,.0f})\n"
            f"  Beds: {self.min_beds:.0f}–{self.max_beds:.0f} | "
            f"Sqft: {self.min_sqft:,}–{self.max_sqft:,}"
        )


# ─── Scoring Functions ────────────────────────────────────────────────────────

def _activity_score(txns_12mo: int, txns_24mo: int) -> float:
    """
    Score based on recent purchase volume.
    Peak: 12+ deals/12mo → 1.0
    Cold: 0 deals/12mo → 0.0
    """
    if txns_12mo >= 12:
        return 1.0
    if txns_12mo >= 8:
        return 0.85
    if txns_12mo >= 5:
        return 0.70
    if txns_12mo >= 3:
        return 0.55
    if txns_12mo >= 1:
        return 0.35
    # Nothing in 12mo — check 24mo for recency
    if txns_24mo >= 3:
        return 0.20
    if txns_24mo >= 1:
        return 0.10
    return 0.0


def _speed_score(avg_days_to_close: float) -> float:
    """
    Score based on average days-to-close. Faster = higher score.
    Unknown (0) = neutral 0.50.
    """
    if avg_days_to_close <= 0:
        return 0.50
    if avg_days_to_close <= 7:
        return 1.0
    if avg_days_to_close <= 14:
        return 0.85
    if avg_days_to_close <= 21:
        return 0.70
    if avg_days_to_close <= 30:
        return 0.55
    if avg_days_to_close <= 45:
        return 0.40
    return 0.25


def _zip_concentration_score(txns: list[BuyerTransaction]) -> float:
    """
    Score based on how concentrated buyer is in specific ZIPs.
    Focused buyer (1–3 ZIPs) = higher score. Scattered = lower.
    """
    if not txns:
        return 0.0
    zips = [t.zip_code for t in txns]
    unique = len(set(zips))
    if unique == 1:
        return 1.0
    if unique <= 3:
        return 0.80
    if unique <= 5:
        return 0.60
    if unique <= 8:
        return 0.40
    return 0.20


def _activity_level(txns_12mo: int, txns_24mo: int) -> str:
    if txns_12mo >= 5:
        return ACTIVITY_HOT
    if txns_12mo >= 2:
        return ACTIVITY_WARM
    if txns_24mo >= 1:
        return ACTIVITY_COLD
    return ACTIVITY_UNKNOWN


# ─── Core: Score a Buyer ──────────────────────────────────────────────────────

def score_buyer(
    buyer_id:   str,
    buyer_name: str,
    txns:       list[BuyerTransaction],
    today:      date | None = None,
) -> BuyerScore:
    """
    Compute composite buyer score from transaction history.
    Used to rank buyers by activity, reliability, and speed.
    """
    today = today or date.today()
    cutoff_12mo = today - timedelta(days=365)
    cutoff_24mo = today - timedelta(days=730)

    txns_12 = [t for t in txns if t.purchase_date and t.purchase_date >= cutoff_12mo]
    txns_24 = [t for t in txns if t.purchase_date and t.purchase_date >= cutoff_24mo]

    txns_12mo = len(txns_12)
    txns_24mo = len(txns_24)

    # Average purchase price (all time)
    prices = [t.purchase_price for t in txns if t.purchase_price > 0]
    avg_price = statistics.mean(prices) if prices else 0.0

    # Average days to close
    close_times = [t.days_to_close for t in txns if t.days_to_close > 0]
    avg_close = statistics.mean(close_times) if close_times else 0.0

    # Active ZIPs (from 12mo txns, or all if no recent)
    recent = txns_12 or txns
    zip_counts: dict[str, int] = {}
    for t in recent:
        zip_counts[t.zip_code] = zip_counts.get(t.zip_code, 0) + 1
    active_zips = sorted(zip_counts, key=lambda z: -zip_counts[z])

    # Component scores
    act   = _activity_score(txns_12mo, txns_24mo)
    spd   = _speed_score(avg_close)
    rel   = min(act + 0.10, 1.0)   # reliability ~ activity with a small boost
    conc  = _zip_concentration_score(txns)

    # Composite: activity 40%, reliability 25%, speed 20%, concentration 15%
    composite = act * 0.40 + rel * 0.25 + spd * 0.20 + conc * 0.15

    return BuyerScore(
        buyer_id           = buyer_id,
        buyer_name         = buyer_name,
        activity_score     = round(act, 3),
        reliability_score  = round(rel, 3),
        speed_score        = round(spd, 3),
        zip_concentration  = round(conc, 3),
        composite_score    = round(composite, 3),
        total_txns         = len(txns),
        txns_12mo          = txns_12mo,
        txns_24mo          = txns_24mo,
        active_zips        = active_zips,
        avg_purchase_price = round(avg_price, -2),
        avg_days_to_close  = round(avg_close, 1),
        activity_level     = _activity_level(txns_12mo, txns_24mo),
    )


# ─── Core: Infer Buy Box ─────────────────────────────────────────────────────

def infer_buy_box(
    buyer_id: str,
    txns:     list[BuyerTransaction],
    today:    date | None = None,
) -> InferredBuyBox | None:
    """
    Infer buy box parameters from transaction history.
    Requires minimum 2 transactions (vault rule).
    Returns None if insufficient data.
    """
    if len(txns) < 2:
        return None

    today = today or date.today()
    cutoff_24mo = today - timedelta(days=730)
    recent = [t for t in txns if t.purchase_date and t.purchase_date >= cutoff_24mo] or txns

    prices   = [t.purchase_price for t in recent if t.purchase_price > 0]
    beds_lst = [t.beds for t in recent if t.beds > 0]
    sqft_lst = [t.sqft for t in recent if t.sqft > 0]

    if not prices:
        return None

    min_p = min(prices)
    max_p = max(prices)
    avg_p = statistics.mean(prices)

    # Add 10% buffer to price band for buy box
    max_p_box = max_p * 1.10

    # ZIP codes from recent transactions
    zip_counts: dict[str, int] = {}
    for t in recent:
        zip_counts[t.zip_code] = zip_counts.get(t.zip_code, 0) + 1
    zips = sorted(zip_counts, key=lambda z: -zip_counts[z])

    # Asset types
    type_counts: dict[str, int] = {}
    for t in recent:
        type_counts[t.property_type] = type_counts.get(t.property_type, 0) + 1
    asset_types = list(type_counts.keys())

    # Confidence: more transactions + more recent = higher confidence
    conf_base = min(len(recent) / 10, 1.0)         # more txns = up to 1.0
    recency_factor = min(len([t for t in txns if t.purchase_date and
                               t.purchase_date >= today - timedelta(days=365)]) / 5, 1.0)
    confidence = round(conf_base * 0.6 + recency_factor * 0.4, 3)

    notes = []
    if len(recent) < 5:
        notes.append("Low transaction count — buy box estimate may drift")
    if len(set(zips)) > 5:
        notes.append("Buyer is active in many ZIPs — may be opportunistic rather than buy-box-driven")

    return InferredBuyBox(
        buyer_id         = buyer_id,
        zip_codes        = zips,
        asset_types      = asset_types,
        min_price        = round(min_p, -3),
        max_price        = round(max_p_box, -3),
        avg_price        = round(avg_p, -2),
        price_band_width = round(max_p_box - min_p, -3),
        min_beds         = min(beds_lst) if beds_lst else 0,
        max_beds         = max(beds_lst) if beds_lst else 0,
        min_sqft         = min(sqft_lst) if sqft_lst else 0,
        max_sqft         = max(sqft_lst) if sqft_lst else 0,
        confidence       = confidence,
        inferred_from_n  = len(recent),
        notes            = notes,
    )


# ─── Vault: Load Buyers from Markdown ────────────────────────────────────────

def _parse_money(text: str) -> float:
    m = re.search(r"\$?([\d,]+)", text or "")
    return float(m.group(1).replace(",", "")) if m else 0.0


def load_buyers_from_vault() -> list[tuple[str, str, list[str]]]:
    """
    Return list of (buyer_id, buyer_name, zip_codes) from all vault buyer files.
    Used for matching and discovery cross-checks.
    """
    results = []
    for path in list_vault("buyers"):
        if path.name == "TEMPLATE.md":
            continue
        content   = path.read_text(encoding="utf-8")
        buyer_id  = path.stem.split("_")[0]
        buyer_name = path.stem.split("_", 1)[-1].replace("_", " ") if "_" in path.stem else path.stem
        zip_codes = list(dict.fromkeys(re.findall(r"\b(\d{5})\b", content)))
        if zip_codes:
            results.append((buyer_id, buyer_name, zip_codes))
    return results


# ─── Discovery: Qualify New Buyer from Transactions ──────────────────────────

def qualify_new_buyer(
    name:        str,
    entity:      str,
    txns:        list[BuyerTransaction],
    source:      str = "propstream",
    today:       date | None = None,
) -> tuple[BuyerScore, InferredBuyBox | None]:
    """
    Qualify a potential new buyer from their transaction history.
    Enforces vault rule: minimum 2 cash transactions required.

    Returns (BuyerScore, InferredBuyBox | None).
    Raises ValueError if buyer does not meet minimum qualification.
    """
    cash_txns = [t for t in txns if t.is_cash]
    if len(cash_txns) < 2:
        raise ValueError(
            f"Buyer '{name}' has only {len(cash_txns)} cash transaction(s). "
            f"Minimum 2 required before creating vault file."
        )

    buyer_id  = "PENDING"  # assigned on vault write
    score     = score_buyer(buyer_id, name, txns, today)
    buy_box   = infer_buy_box(buyer_id, txns, today)

    return score, buy_box


def create_buyer_vault_file(
    name:       str,
    entity:     str,
    score:      BuyerScore,
    buy_box:    InferredBuyBox | None,
    txns:       list[BuyerTransaction],
    source:     str = "propstream",
) -> str:
    """
    Write a new buyer vault file to buyers/ and return the new buyer_id.
    Only call after qualify_new_buyer() passes.
    """
    today    = date.today().isoformat()
    buyer_id = next_id("BUY", "buyers")
    slug     = name.replace(" ", "_").replace(",", "")[:25]
    filename = f"{buyer_id}_{slug}.md"

    zip_list = "\n".join(f"- {z}" for z in score.active_zips[:10])

    # Price range line
    if buy_box:
        price_line = f"$**{buy_box.min_price:,.0f}** – **${buy_box.max_price:,.0f}**"
        bed_line   = f"{buy_box.min_beds:.0f}+"
        sqft_line  = f"{buy_box.min_sqft:,} – {buy_box.max_sqft:,} sqft"
    else:
        price_line = "Unknown — infer from transactions"
        bed_line   = "Unknown"
        sqft_line  = "Unknown"

    recent_txn_lines = ""
    for t in sorted(txns, key=lambda x: x.purchase_date or date.min, reverse=True)[:5]:
        recent_txn_lines += f"- {t.purchase_date} · {t.address} ({t.zip_code}) · ${t.purchase_price:,.0f}\n"

    content = f"""# {name}

## ZIP Codes
{zip_list}

## Buy Box
- **Property Type:** {', '.join(buy_box.asset_types) if buy_box else 'SFR'}
- **Price Range:** {price_line}
- **Beds:** {bed_line}
- **Sqft:** {sqft_line}
- **Strategy:** {score.activity_level}
- **Condition:** Unknown

## Deal Activity
- **12mo:** {score.txns_12mo} deals
- **24mo:** {score.txns_24mo} deals
- **Total:** {score.total_txns} deals
- **Avg Price:** ${score.avg_purchase_price:,.0f}
- **Avg Close:** {score.avg_days_to_close:.0f} days

## Recent Transactions
{recent_txn_lines}
## Notes
- Source: {source}
- Activity: {score.activity_level.upper()} (score {score.composite_score:.2f})
{"- Buy box inferred from " + str(score.total_txns) + " transactions (confidence " + str(buy_box.confidence if buy_box else 0) + ")" if buy_box else ""}

---

<!-- AMARA OS Extended Fields -->

## Identity
- **ID:** {buyer_id}
- **Entity:** {entity}
- **Status:** {BUYER_STATUS_ACTIVE}
- **Created:** {today}
- **Source:** {source}

## Scores
- **Activity:** {score.activity_score:.2f}
- **Reliability:** {score.reliability_score:.2f}
- **Speed:** {score.speed_score:.2f}
- **Composite:** {score.composite_score:.2f}
"""

    write_vault_file("buyers", filename, content)
    return buyer_id


# ─── Rank All Vault Buyers ────────────────────────────────────────────────────

def rank_vault_buyers(
    txns_by_buyer: dict[str, list[BuyerTransaction]],
    today: date | None = None,
) -> list[BuyerScore]:
    """
    Score and rank all buyers in the vault.
    txns_by_buyer: dict mapping buyer_id → list of transactions.
    Returns list of BuyerScore sorted by composite_score descending.
    """
    scores = []
    vault_buyers = load_buyers_from_vault()
    id_to_name   = {bid: name for bid, name, _ in vault_buyers}

    for buyer_id, txns in txns_by_buyer.items():
        name  = id_to_name.get(buyer_id, buyer_id)
        score = score_buyer(buyer_id, name, txns, today)
        scores.append(score)

    scores.sort(key=lambda s: -s.composite_score)
    return scores


# ─── ZIP Liquidity Snapshot ───────────────────────────────────────────────────

@dataclass
class ZipLiquiditySnapshot:
    zip_code:            str
    active_buyer_count:  int   = 0
    avg_days_to_close:   float = 0.0
    median_buy_price:    float = 0.0
    deal_count_90d:      int   = 0
    deal_count_180d:     int   = 0
    demand_score:        float = 0.0     # 0.0–1.0

    def label(self) -> str:
        if self.demand_score >= 0.75: return "HIGH DEMAND"
        if self.demand_score >= 0.50: return "MODERATE"
        if self.demand_score >= 0.25: return "LOW"
        return "UNKNOWN"


def compute_zip_liquidity(
    zip_code: str,
    txns:     list[BuyerTransaction],
    today:    date | None = None,
) -> ZipLiquiditySnapshot:
    """
    Compute demand / liquidity stats for a single ZIP from transaction data.
    """
    today = today or date.today()
    cutoff_90d  = today - timedelta(days=90)
    cutoff_180d = today - timedelta(days=180)

    zip_txns     = [t for t in txns if t.zip_code == zip_code]
    txns_90d     = [t for t in zip_txns if t.purchase_date and t.purchase_date >= cutoff_90d]
    txns_180d    = [t for t in zip_txns if t.purchase_date and t.purchase_date >= cutoff_180d]

    buyer_ids    = set(id(t) for t in zip_txns)   # proxy count
    prices       = [t.purchase_price for t in zip_txns if t.purchase_price > 0]
    close_times  = [t.days_to_close for t in zip_txns if t.days_to_close > 0]

    median_price = sorted(prices)[len(prices)//2] if prices else 0.0
    avg_close    = statistics.mean(close_times) if close_times else 0.0

    # Demand score: weighted by 90d volume (50%), 180d volume (30%), close speed (20%)
    vol90_score  = min(len(txns_90d) / 10, 1.0)
    vol180_score = min(len(txns_180d) / 20, 1.0)
    spd_score    = _speed_score(avg_close)
    demand       = vol90_score * 0.50 + vol180_score * 0.30 + spd_score * 0.20

    return ZipLiquiditySnapshot(
        zip_code           = zip_code,
        active_buyer_count = len(set(t.zip_code for t in txns_90d)),  # unique ZIPs active = proxy
        avg_days_to_close  = round(avg_close, 1),
        median_buy_price   = round(median_price, -2),
        deal_count_90d     = len(txns_90d),
        deal_count_180d    = len(txns_180d),
        demand_score       = round(demand, 3),
    )


def print_buyer_rankings(scores: list[BuyerScore]) -> None:
    print(f"\n{'═' * 60}")
    print(f"BUYER RANKINGS — {len(scores)} buyers scored")
    print(f"{'─' * 60}")
    for i, s in enumerate(scores, 1):
        print(f"  {i:2}. {s.summary()}")
    print(f"{'═' * 60}\n")
