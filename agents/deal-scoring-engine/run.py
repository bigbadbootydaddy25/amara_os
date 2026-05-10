"""
Deal Scoring Engine — AI_BRAIN
Integrates portfolio-distress signals into deal scores.

Datasets:
  data/portfolio-distress/DISTRESSED_PORTFOLIOS.json
  data/portfolio-distress/OVERLEVERAGED_BUYERS.json
  data/portfolio-distress/STALLED_BUILDERS.json

Rules:
  - Boost seller-side opportunity when owner portfolio distress is high
  - Downgrade buyer/dispo priority when buyer is overleveraged
  - Flag stalled builders as motivated sellers, not buyers
  - Preserve source evidence on every scored output
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "portfolio-distress"

DISTRESSED_PORTFOLIOS_PATH = DATA_DIR / "DISTRESSED_PORTFOLIOS.json"
OVERLEVERAGED_BUYERS_PATH = DATA_DIR / "OVERLEVERAGED_BUYERS.json"
STALLED_BUILDERS_PATH = DATA_DIR / "STALLED_BUILDERS.json"

DEALS_PATH = ROOT / "data" / "deals.json"
LATEST_DIR = ROOT / "latest"

# ── Types ──────────────────────────────────────────────────────────────────────

DealSide = Literal["acquisition", "disposition", "jv", "land"]
BuilderRole = Literal["motivated_seller", "cautious_seller", "qualified_buyer"]
DispoPriority = Literal["high", "standard", "downgraded", "disqualified"]


@dataclass
class SourceEvidence:
    dataset: str
    record_id: str
    signals: list[str]
    raw_score: int
    intel_date: str | None = None


@dataclass
class SellerOpportunityResult:
    base_score: int
    distress_boost: int
    final_score: int
    distress_match: bool
    motivation_signals: list[str]
    evidence: SourceEvidence | None


@dataclass
class BuyerPriorityResult:
    base_score: int
    leverage_penalty: int
    final_score: int
    dispo_priority: DispoPriority
    risk_flags: list[str]
    evidence: SourceEvidence | None


@dataclass
class BuilderRoleResult:
    classified_role: BuilderRole
    stall_score: int
    qualified_as_buyer: bool
    motivation_signals: list[str]
    evidence: SourceEvidence | None


@dataclass
class DealScore:
    deal_id: str
    deal_side: DealSide
    counterparty_id: str
    counterparty_name: str
    composite_score: int
    recommendation: str
    scored_at: str
    seller_opportunity: SellerOpportunityResult | None = None
    buyer_priority: BuyerPriorityResult | None = None
    builder_role: BuilderRoleResult | None = None


# ── Data loading ──────────────────────────────────────────────────────────────

def _load(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return json.load(f)


_portfolios: list[dict] | None = None
_buyers: list[dict] | None = None
_builders: list[dict] | None = None
_deals: list[dict] | None = None


def portfolios() -> list[dict]:
    global _portfolios
    if _portfolios is None:
        _portfolios = _load(DISTRESSED_PORTFOLIOS_PATH)["portfolios"]
    return _portfolios


def buyers() -> list[dict]:
    global _buyers
    if _buyers is None:
        _buyers = _load(OVERLEVERAGED_BUYERS_PATH)["buyers"]
    return _buyers


def builders() -> list[dict]:
    global _builders
    if _builders is None:
        _builders = _load(STALLED_BUILDERS_PATH)["builders"]
    return _builders


def pipeline_deals() -> list[dict]:
    global _deals
    if _deals is None:
        if DEALS_PATH.exists():
            _deals = _load(DEALS_PATH)["deals"]
        else:
            _deals = []
    return _deals


# ── Entity-name matching against distress datasets ────────────────────────────
# Pipeline deals carry entity names (owner_name, buyer_name, builder_name).
# These lookups resolve names to distress records without requiring pre-keyed IDs.

def _portfolio_by_name(name: str | None) -> dict | None:
    if not name:
        return None
    name_lower = name.strip().lower()
    return next((p for p in portfolios() if p["owner"].strip().lower() == name_lower), None)


def _buyer_by_name(name: str | None) -> dict | None:
    if not name:
        return None
    name_lower = name.strip().lower()
    return next((b for b in buyers() if b["name"].strip().lower() == name_lower), None)


def _builder_by_name(name: str | None) -> dict | None:
    if not name:
        return None
    name_lower = name.strip().lower()
    return next((b for b in builders() if b["name"].strip().lower() == name_lower), None)


# ── Seller-side: boost when owner portfolio distress is high ──────────────────
# Boost formula: distress_score (0–100) → max +40 at score 100

def score_seller_opportunity(owner_id: str, base_score: int = 50) -> SellerOpportunityResult:
    portfolio = next((p for p in portfolios() if p["id"] == owner_id), None)

    if portfolio is None:
        return SellerOpportunityResult(
            base_score=base_score,
            distress_boost=0,
            final_score=base_score,
            distress_match=False,
            motivation_signals=[],
            evidence=None,
        )

    ind = portfolio["distress_indicators"]
    distress_score = portfolio["distress_score"]
    boost = round((distress_score / 100) * 40)
    final = min(100, base_score + boost)

    evidence = SourceEvidence(
        dataset="DISTRESSED_PORTFOLIOS",
        record_id=portfolio["id"],
        signals=[
            f"distress_score: {distress_score}",
            f"weighted_vacancy: {ind['weighted_vacancy_rate'] * 100:.0f}%",
            f"DSCR: {ind['debt_service_coverage_ratio']}",
            f"delinquency_days: {ind['loan_delinquency_days']}",
            f"foreclosure_notices: {ind['foreclosure_notices']}",
            f"maturity_wall_months: {ind['maturity_wall_months']}",
        ],
        raw_score=distress_score,
        intel_date=portfolio["source_evidence"]["market_intel_date"],
    )

    return SellerOpportunityResult(
        base_score=base_score,
        distress_boost=boost,
        final_score=final,
        distress_match=True,
        motivation_signals=portfolio["motivation_signals"],
        evidence=evidence,
    )


# ── Buyer-side: downgrade priority when buyer is overleveraged ────────────────
# Penalty formula: leverage_score (0–100) → max -45 at score 100

def score_buyer_priority(buyer_id: str, base_score: int = 50) -> BuyerPriorityResult:
    buyer = next((b for b in buyers() if b["id"] == buyer_id), None)

    if buyer is None:
        return BuyerPriorityResult(
            base_score=base_score,
            leverage_penalty=0,
            final_score=base_score,
            dispo_priority="standard",
            risk_flags=[],
            evidence=None,
        )

    ind = buyer["leverage_indicators"]
    posture = buyer["acquisition_posture"]
    leverage_score = buyer["leverage_score"]
    penalty = round((leverage_score / 100) * 45)
    final = max(0, base_score - penalty)

    if leverage_score >= 80:
        priority: DispoPriority = "disqualified"
    elif leverage_score >= 60:
        priority = "downgraded"
    elif leverage_score >= 35:
        priority = "standard"
    else:
        priority = "high"

    evidence = SourceEvidence(
        dataset="OVERLEVERAGED_BUYERS",
        record_id=buyer["id"],
        signals=[
            f"leverage_score: {leverage_score}",
            f"portfolio_ltv: {ind['portfolio_ltv'] * 100:.0f}%",
            f"debt_to_equity: {ind['debt_to_equity_ratio']}",
            f"interest_coverage: {ind['interest_coverage_ratio']}",
            f"loans_in_extension: {ind['loans_in_extension']}",
            f"escrow_failures_12mo: {posture['deals_fallen_out_of_escrow_12mo']}",
        ],
        raw_score=leverage_score,
        intel_date=buyer["source_evidence"]["intel_date"],
    )

    return BuyerPriorityResult(
        base_score=base_score,
        leverage_penalty=penalty,
        final_score=final,
        dispo_priority=priority,
        risk_flags=buyer["risk_flags"],
        evidence=evidence,
    )


# ── Builder classification: stalled → motivated seller, not buyer ─────────────

def classify_builder_role(builder_id: str) -> BuilderRoleResult:
    builder = next((b for b in builders() if b["id"] == builder_id), None)

    if builder is None:
        return BuilderRoleResult(
            classified_role="qualified_buyer",
            stall_score=0,
            qualified_as_buyer=True,
            motivation_signals=[],
            evidence=None,
        )

    role: BuilderRole = builder["role_classification"]
    fd = builder["financial_distress"]

    evidence = SourceEvidence(
        dataset="STALLED_BUILDERS",
        record_id=builder["id"],
        signals=[
            f"stall_score: {builder['stall_score']}",
            f"role: {role}",
            f"disqualification: {builder['buyer_disqualification_reason']}",
            f"mechanic_liens_filed: {fd['mechanic_liens_filed']}",
            f"construction_loan_status: {fd['construction_loan_status']}",
            f"cost_gap: ${fd['estimated_completion_cost_gap']:,}",
        ],
        raw_score=builder["stall_score"],
        intel_date=builder["source_evidence"].get("intel_date"),
    )

    return BuilderRoleResult(
        classified_role=role,
        stall_score=builder["stall_score"],
        qualified_as_buyer=(role == "qualified_buyer"),
        motivation_signals=builder["motivation_signals"],
        evidence=evidence,
    )


# ── Recommendation builders ───────────────────────────────────────────────────

def _seller_recommendation(result: SellerOpportunityResult) -> str:
    if not result.distress_match:
        return "No portfolio distress signals — evaluate on standard fundamentals."
    score = result.evidence.raw_score if result.evidence else 0
    first_signal = result.motivation_signals[0] if result.motivation_signals else ""
    if result.final_score >= 80:
        return (
            f"HIGH OPPORTUNITY — seller portfolio distress is severe (score {score}/100). "
            f"Prioritise outreach and structure for speed. {first_signal}"
        )
    if result.final_score >= 65:
        return (
            f"ELEVATED OPPORTUNITY — meaningful distress detected (score {score}/100). "
            f"Engage with creative structuring. {first_signal}"
        )
    return (
        f"MODERATE OPPORTUNITY — early-stage distress (score {score}/100). "
        "Monitor cadence and maintain relationship."
    )


def _buyer_recommendation(result: BuyerPriorityResult) -> str:
    score = result.evidence.raw_score if result.evidence else 0
    first_flag = result.risk_flags[0] if result.risk_flags else ""
    if result.dispo_priority == "disqualified":
        return (
            f"DO NOT PRIORITISE — buyer is severely overleveraged (leverage score {score}/100). "
            f"High escrow failure risk. {first_flag}"
        )
    if result.dispo_priority == "downgraded":
        return (
            f"DOWNGRADED — buyer carries significant leverage risk (score {score}/100). "
            f"Require proof of funds and shorter contingency periods. {first_flag}"
        )
    if result.dispo_priority == "standard":
        return "STANDARD — buyer leverage is manageable. Proceed with normal diligence."
    return "HIGH PRIORITY BUYER — clean balance sheet and strong close track record."


def _builder_recommendation(result: BuilderRoleResult) -> str:
    score = result.stall_score
    first_signal = result.motivation_signals[0] if result.motivation_signals else ""
    dataset = result.evidence.dataset if result.evidence else "STALLED_BUILDERS"
    record_id = result.evidence.record_id if result.evidence else "unknown"
    return (
        f"RECLASSIFY AS SELLER — this builder is stalled (stall score {score}/100) and should be "
        f"treated as a motivated seller, not a buyer. {first_signal} "
        f"Source: {dataset} [{record_id}]"
    )


# ── Composite deal scorer ─────────────────────────────────────────────────────

def score_deal(
    deal_id: str,
    deal_side: DealSide,
    counterparty_id: str,
    counterparty_name: str,
    base_score: int = 50,
) -> DealScore:
    now = datetime.now(timezone.utc).isoformat()

    if deal_side in ("acquisition", "land"):
        seller = score_seller_opportunity(counterparty_id, base_score)
        return DealScore(
            deal_id=deal_id,
            deal_side=deal_side,
            counterparty_id=counterparty_id,
            counterparty_name=counterparty_name,
            composite_score=seller.final_score,
            recommendation=_seller_recommendation(seller),
            scored_at=now,
            seller_opportunity=seller,
        )

    if deal_side == "disposition":
        buyer = score_buyer_priority(counterparty_id, base_score)
        builder = classify_builder_role(counterparty_id)
        is_builder = builder.evidence is not None

        if is_builder and not builder.qualified_as_buyer:
            return DealScore(
                deal_id=deal_id,
                deal_side=deal_side,
                counterparty_id=counterparty_id,
                counterparty_name=counterparty_name,
                composite_score=0,
                recommendation=_builder_recommendation(builder),
                scored_at=now,
                buyer_priority=buyer,
                builder_role=builder,
            )

        return DealScore(
            deal_id=deal_id,
            deal_side=deal_side,
            counterparty_id=counterparty_id,
            counterparty_name=counterparty_name,
            composite_score=buyer.final_score,
            recommendation=_buyer_recommendation(buyer),
            scored_at=now,
            buyer_priority=buyer,
            builder_role=builder if is_builder else None,
        )

    # JV — surface whichever signal is most acute
    seller = score_seller_opportunity(counterparty_id, base_score)
    buyer = score_buyer_priority(counterparty_id, base_score)
    builder = classify_builder_role(counterparty_id)

    if builder.evidence and not builder.qualified_as_buyer:
        recommendation = _builder_recommendation(builder)
        composite = 0
    elif seller.distress_match:
        recommendation = _seller_recommendation(seller)
        composite = seller.final_score
    elif buyer.evidence:
        recommendation = _buyer_recommendation(buyer)
        composite = buyer.final_score
    else:
        recommendation = "No distress signals found — score based on standard underwriting."
        composite = base_score

    return DealScore(
        deal_id=deal_id,
        deal_side=deal_side,
        counterparty_id=counterparty_id,
        counterparty_name=counterparty_name,
        composite_score=composite,
        recommendation=recommendation,
        scored_at=now,
        seller_opportunity=seller if seller.distress_match else None,
        buyer_priority=buyer if buyer.evidence else None,
        builder_role=builder if builder.evidence else None,
    )


# ── Batch helpers ─────────────────────────────────────────────────────────────

def score_pipeline_deal(deal: dict) -> DealScore:
    """Score a raw pipeline deal record, applying distress overlays by entity name."""
    deal_id: str = deal["deal_id"]
    deal_side: DealSide = deal["deal_side"]
    base_score: int = deal.get("base_score", 50)
    now = datetime.now(timezone.utc).isoformat()

    owner_name: str | None = deal.get("owner_name")
    buyer_name: str | None = deal.get("buyer_name")
    builder_name: str | None = deal.get("builder_name")

    # Resolve entity names to distress records
    portfolio_rec = _portfolio_by_name(owner_name)
    buyer_rec = _buyer_by_name(buyer_name)
    builder_rec = _builder_by_name(builder_name)

    # Use the pre-keyed ID-based functions when a match exists, else pass a sentinel
    seller_id = portfolio_rec["id"] if portfolio_rec else "__no_match__"
    buyer_id = buyer_rec["id"] if buyer_rec else "__no_match__"
    builder_id = builder_rec["id"] if builder_rec else "__no_match__"

    counterparty_name = owner_name or buyer_name or builder_name or "Unknown"

    if deal_side in ("acquisition", "land"):
        seller = score_seller_opportunity(seller_id, base_score)
        return DealScore(
            deal_id=deal_id,
            deal_side=deal_side,
            counterparty_id=seller_id,
            counterparty_name=counterparty_name,
            composite_score=seller.final_score,
            recommendation=_seller_recommendation(seller),
            scored_at=now,
            seller_opportunity=seller,
        )

    if deal_side == "disposition":
        buyer = score_buyer_priority(buyer_id, base_score)
        builder = classify_builder_role(builder_id)
        is_builder = builder.evidence is not None

        if is_builder and not builder.qualified_as_buyer:
            return DealScore(
                deal_id=deal_id,
                deal_side=deal_side,
                counterparty_id=builder_id,
                counterparty_name=counterparty_name,
                composite_score=0,
                recommendation=_builder_recommendation(builder),
                scored_at=now,
                buyer_priority=buyer,
                builder_role=builder,
            )

        return DealScore(
            deal_id=deal_id,
            deal_side=deal_side,
            counterparty_id=buyer_id,
            counterparty_name=counterparty_name,
            composite_score=buyer.final_score,
            recommendation=_buyer_recommendation(buyer),
            scored_at=now,
            buyer_priority=buyer,
            builder_role=builder if is_builder else None,
        )

    # JV
    seller = score_seller_opportunity(seller_id, base_score)
    buyer = score_buyer_priority(buyer_id, base_score)
    builder = classify_builder_role(builder_id)

    if builder.evidence and not builder.qualified_as_buyer:
        recommendation = _builder_recommendation(builder)
        composite = 0
        cp_id = builder_id
    elif seller.distress_match:
        recommendation = _seller_recommendation(seller)
        composite = seller.final_score
        cp_id = seller_id
    elif buyer.evidence:
        recommendation = _buyer_recommendation(buyer)
        composite = buyer.final_score
        cp_id = buyer_id
    else:
        recommendation = "No distress signals — score based on standard underwriting."
        composite = base_score
        cp_id = "__no_match__"

    return DealScore(
        deal_id=deal_id,
        deal_side=deal_side,
        counterparty_id=cp_id,
        counterparty_name=counterparty_name,
        composite_score=composite,
        recommendation=recommendation,
        scored_at=now,
        seller_opportunity=seller if seller.distress_match else None,
        buyer_priority=buyer if buyer.evidence else None,
        builder_role=builder if builder.evidence else None,
    )


def score_pipeline() -> list[DealScore]:
    return [score_pipeline_deal(d) for d in pipeline_deals()]


def score_all_distressed_portfolios(base_score: int = 50) -> list[DealScore]:
    return [
        score_deal(
            deal_id=f"AUTO-{p['id']}",
            deal_side="acquisition",
            counterparty_id=p["id"],
            counterparty_name=p["owner"],
            base_score=base_score,
        )
        for p in portfolios()
    ]


def score_all_buyers(base_score: int = 50) -> list[DealScore]:
    return [
        score_deal(
            deal_id=f"AUTO-{b['id']}",
            deal_side="disposition",
            counterparty_id=b["id"],
            counterparty_name=b["name"],
            base_score=base_score,
        )
        for b in buyers()
    ]


def score_all_builders(base_score: int = 50) -> list[DealScore]:
    return [
        score_deal(
            deal_id=f"AUTO-{b['id']}",
            deal_side="disposition",
            counterparty_id=b["id"],
            counterparty_name=b["name"],
            base_score=base_score,
        )
        for b in builders()
    ]


# ── Serialisation ─────────────────────────────────────────────────────────────

def _serialise(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _serialise(v) for k, v in asdict(obj).items() if v is not None}
    if isinstance(obj, list):
        return [_serialise(i) for i in obj]
    return obj


# ── Scorecard writer ─────────────────────────────────────────────────────────

def _distress_summary_table(scores: list[DealScore]) -> str:
    """Build the Portfolio Distress Signals register from scored deals."""
    hits: list[tuple[str, str, int, int, str]] = []  # deal_id, name, distress_raw, final, recommendation

    for ds in scores:
        if ds.seller_opportunity and ds.seller_opportunity.distress_match and ds.seller_opportunity.evidence:
            ev = ds.seller_opportunity.evidence
            hits.append((
                ds.deal_id,
                ds.counterparty_name,
                ev.raw_score,
                ds.composite_score,
                ds.recommendation[:80],
            ))

    if not hits:
        return "_No distressed portfolio owners matched in this run._\n"

    lines = [
        "| Deal | Owner | Distress Score | Final Score | Signal |",
        "|---|---|---|---|---|",
    ]
    for deal_id, name, raw, final, rec in sorted(hits, key=lambda x: -x[2]):
        lines.append(f"| {deal_id} | {name} | {raw}/100 | **{final}/100** | {rec} |")
    return "\n".join(lines) + "\n"


def _overleveraged_summary_table(scores: list[DealScore]) -> str:
    hits = []
    for ds in scores:
        if ds.buyer_priority and ds.buyer_priority.evidence and ds.buyer_priority.dispo_priority in ("downgraded", "disqualified"):
            ev = ds.buyer_priority.evidence
            hits.append((ds.deal_id, ds.counterparty_name, ev.raw_score, ds.composite_score, ds.buyer_priority.dispo_priority))

    if not hits:
        return "_No overleveraged buyers matched in this run._\n"

    lines = [
        "| Deal | Buyer | Leverage Score | Final Score | Priority |",
        "|---|---|---|---|---|",
    ]
    for deal_id, name, raw, final, priority in sorted(hits, key=lambda x: -x[2]):
        lines.append(f"| {deal_id} | {name} | {raw}/100 | **{final}/100** | `{priority}` |")
    return "\n".join(lines) + "\n"


def _stalled_builder_summary_table(scores: list[DealScore]) -> str:
    hits = []
    for ds in scores:
        if ds.builder_role and ds.builder_role.evidence and not ds.builder_role.qualified_as_buyer:
            ev = ds.builder_role.evidence
            hits.append((ds.deal_id, ds.counterparty_name, ev.raw_score, ds.builder_role.classified_role))

    if not hits:
        return "_No stalled builders matched in this run._\n"

    lines = [
        "| Deal | Builder | Stall Score | Classification |",
        "|---|---|---|---|",
    ]
    for deal_id, name, raw, role in sorted(hits, key=lambda x: -x[2]):
        lines.append(f"| {deal_id} | {name} | {raw}/100 | `{role}` |")
    return "\n".join(lines) + "\n"


def write_latest_scorecard(pipeline_scores: list[DealScore]) -> Path:
    """Write latest/DEAL_SCORECARD.md with a Portfolio Distress Signals section."""
    LATEST_DIR.mkdir(exist_ok=True)
    out = LATEST_DIR / "DEAL_SCORECARD.md"
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = len(pipeline_scores)
    distress_hits = sum(
        1 for ds in pipeline_scores
        if ds.seller_opportunity and ds.seller_opportunity.distress_match
    )
    leverage_hits = sum(
        1 for ds in pipeline_scores
        if ds.buyer_priority and ds.buyer_priority.dispo_priority in ("downgraded", "disqualified")
    )
    builder_hits = sum(
        1 for ds in pipeline_scores
        if ds.builder_role and not ds.builder_role.qualified_as_buyer
    )

    high = [ds for ds in pipeline_scores if ds.composite_score >= 80]
    elevated = [ds for ds in pipeline_scores if 65 <= ds.composite_score < 80]
    deprioritised = [ds for ds in pipeline_scores if ds.composite_score < 35]

    content = f"""# Deal Scorecard

**Agent:** `agents/deal-scoring-engine/run.py`
**Run date:** {run_date}
**Pipeline deals scored:** {total}

---

## Run Summary

| Metric | Count |
|---|---|
| Total deals scored | {total} |
| Distress-boosted (seller) | {distress_hits} |
| Leverage-penalised (buyer) | {leverage_hits} |
| Builders reclassified as sellers | {builder_hits} |
| HIGH PRIORITY (≥80) | {len(high)} |
| ELEVATED (65–79) | {len(elevated)} |
| DEPRIORITISE (<35) | {len(deprioritised)} |

---

## Portfolio Distress Signals

Portfolio distress is the primary upward driver of seller-side opportunity scores. Owner names are matched against `data/portfolio-distress/DISTRESSED_PORTFOLIOS.json` at score time.

### Signal Hierarchy

| Rank | Signal | High Distress Threshold |
|---|---|---|
| 1 | Foreclosure notices filed | ≥ 1 |
| 2 | Loan delinquency | > 90 days |
| 3 | Maturity wall | ≤ 6 months |
| 4 | DSCR | < 0.80 |
| 5 | Weighted portfolio vacancy | > 30% |
| 6 | Negative cash flow streak | ≥ 6 consecutive months |

### Boost Formula

```
distress_boost = round((distress_score / 100) × 40)
final_score    = min(100, base_score + distress_boost)
```

### Distressed Owners Matched This Run

{_distress_summary_table(pipeline_scores)}

---

## Overleveraged Buyers — Dispo Downgrades

Buyer names are matched against `data/portfolio-distress/OVERLEVERAGED_BUYERS.json`. Leverage penalty applied:

```
leverage_penalty = round((leverage_score / 100) × 45)
final_score      = max(0, base_score - leverage_penalty)
```

### Overleveraged Buyers Matched This Run

{_overleveraged_summary_table(pipeline_scores)}

---

## Stalled Builders — Role Reclassification

Builder names are matched against `data/portfolio-distress/STALLED_BUILDERS.json`. Stalled builders are treated as motivated sellers; composite score is forced to 0 on the buyer side.

### Builders Reclassified This Run

{_stalled_builder_summary_table(pipeline_scores)}

---

## HIGH PRIORITY Deals (score ≥ 80)

| Deal | Counterparty | Side | Score | Recommendation |
|---|---|---|---|---|
{"".join(f"| {ds.deal_id} | {ds.counterparty_name} | {ds.deal_side} | **{ds.composite_score}** | {ds.recommendation[:90]} |" + chr(10) for ds in sorted(high, key=lambda x: -x.composite_score)) or "_None this run._" + chr(10)}

---

## Source Files

| File | Purpose |
|---|---|
| `data/deals.json` | Active deal pipeline |
| `data/portfolio-distress/DISTRESSED_PORTFOLIOS.json` | Distressed portfolio owners |
| `data/portfolio-distress/OVERLEVERAGED_BUYERS.json` | Overleveraged buyers |
| `data/portfolio-distress/STALLED_BUILDERS.json` | Stalled builders |
| `agents/deal-scoring-engine/run.py` | Scoring agent |
"""

    out.write_text(content)
    return out


# ── CLI output ────────────────────────────────────────────────────────────────

BAND = {
    (80, 100): "HIGH PRIORITY",
    (65, 79): "ELEVATED",
    (50, 64): "STANDARD",
    (35, 49): "CAUTIOUS",
    (0, 34): "DEPRIORITISE",
}


def _band(score: int) -> str:
    for (lo, hi), label in BAND.items():
        if lo <= score <= hi:
            return label
    return "UNKNOWN"


def _print_score(ds: DealScore, verbose: bool = False) -> None:
    band = _band(ds.composite_score)
    print(f"\n{'─' * 64}")
    print(f"  {ds.deal_id}  |  {ds.counterparty_name}")
    print(f"  Side: {ds.deal_side:<14}  Score: {ds.composite_score:>3}/100  [{band}]")
    print(f"  {ds.recommendation}")

    if verbose and ds.seller_opportunity and ds.seller_opportunity.evidence:
        ev = ds.seller_opportunity.evidence
        print(f"\n  [Evidence — {ev.dataset} / {ev.record_id}]")
        for sig in ev.signals:
            print(f"    · {sig}")
        if ev.intel_date:
            print(f"    · intel_date: {ev.intel_date}")

    if verbose and ds.buyer_priority and ds.buyer_priority.evidence:
        ev = ds.buyer_priority.evidence
        print(f"\n  [Evidence — {ev.dataset} / {ev.record_id}]")
        for sig in ev.signals:
            print(f"    · {sig}")

    if verbose and ds.builder_role and ds.builder_role.evidence:
        ev = ds.builder_role.evidence
        print(f"\n  [Evidence — {ev.dataset} / {ev.record_id}]")
        for sig in ev.signals:
            print(f"    · {sig}")


def main() -> None:
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    as_json = "--json" in sys.argv

    print("=" * 64)
    print("  AI_BRAIN DEAL SCORING ENGINE")
    print("  Portfolio Distress Integration")
    print("=" * 64)

    # ── Score the deal pipeline ───────────────────────────────────────────────
    pipe_scores = score_pipeline()
    total_pipeline = len(pipe_scores)

    if total_pipeline:
        print(f"\n{'━' * 64}")
        print(f"  DEAL PIPELINE  ({total_pipeline} deals)")
        print(f"{'━' * 64}")
        for ds in pipe_scores:
            _print_score(ds, verbose=verbose)
    else:
        print("\n  [PIPELINE] No deals found in data/deals.json — skipping pipeline run.")

    # ── Write latest/DEAL_SCORECARD.md ────────────────────────────────────────
    scorecard_path = write_latest_scorecard(pipe_scores)
    print(f"\n  Scorecard written → {scorecard_path.relative_to(ROOT)}")

    # ── Distress dataset batch runs (for audit/debug) ─────────────────────────
    sections = [
        ("DISTRESSED PORTFOLIO OWNERS — Seller Opportunity", score_all_distressed_portfolios()),
        ("OVERLEVERAGED BUYERS — Dispo Priority", score_all_buyers()),
        ("STALLED BUILDERS — Role Classification", score_all_builders()),
    ]

    all_scores: list[DealScore] = list(pipe_scores)

    for header, scores in sections:
        print(f"\n{'━' * 64}")
        print(f"  {header}")
        print(f"{'━' * 64}")
        for ds in scores:
            _print_score(ds, verbose=verbose)
            all_scores.append(ds)

    print(f"\n{'═' * 64}")
    print(f"  Pipeline: {total_pipeline} deals  |  Distress datasets: {len(all_scores) - total_pipeline} records")
    print(f"  Total scored: {len(all_scores)}  |  {datetime.now(timezone.utc).date()}")
    print(f"{'═' * 64}\n")

    if as_json:
        print(json.dumps([_serialise(s) for s in all_scores], indent=2))


if __name__ == "__main__":
    main()
