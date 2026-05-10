# Deal Scorecard

Reference guide for how the AI_BRAIN deal-scoring engine computes and adjusts deal scores.

**Agent:** `agents/deal-scoring-engine/run.py`
**Run:** `python3 agents/deal-scoring-engine/run.py [--verbose] [--json]`

---

## Scoring Overview

All deals are scored 0–100. A base score of 50 is assumed unless overridden. Distress signals, leverage data, and builder stall status adjust the score up or down from that base.

| Score Band | Label | Interpretation |
|---|---|---|
| 80–100 | HIGH PRIORITY | Act immediately |
| 65–79 | ELEVATED | Engage with urgency |
| 50–64 | STANDARD | Normal underwriting cadence |
| 35–49 | CAUTIOUS | Additional diligence required |
| 0–34 | DEPRIORITISE | Do not advance without resolution |

---

## Scoring Modules

### 1. `score_seller_opportunity(owner_id, base_score=50)`

Applied when `deal_side` is `acquisition` or `land`.

Matches owner against `DISTRESSED_PORTFOLIOS.json`. Distress boost is proportional to `distress_score`:

```
distress_boost = round((distress_score / 100) × 40)
final_score    = min(100, base_score + distress_boost)
```

### 2. `score_buyer_priority(buyer_id, base_score=50)`

Applied when `deal_side` is `disposition`.

Matches buyer against `OVERLEVERAGED_BUYERS.json`. Leverage penalty is proportional to `leverage_score`:

```
leverage_penalty = round((leverage_score / 100) × 45)
final_score      = max(0, base_score - leverage_penalty)
```

**Dispo priority tiers:**

| Leverage Score | Priority |
|---|---|
| 0–34 | `high` |
| 35–59 | `standard` |
| 60–79 | `downgraded` |
| 80–100 | `disqualified` |

### 3. `classify_builder_role(builder_id)`

Applied to any counterparty matched in `STALLED_BUILDERS.json`.

Stalled builders are **reclassified as sellers** — composite score is forced to 0 when they appear on the buyer side:

| Classification | Qualified as Buyer | Score Treatment |
|---|---|---|
| `motivated_seller` | No | Score → 0; seller outreach recommended |
| `cautious_seller` | No | Score → 0; evaluate as seller lead |
| `qualified_buyer` | Yes | Normal buyer scoring applies |

---

## Portfolio Distress Signals

Portfolio distress is the primary upward driver of seller-side opportunity scores. This section documents the signals, their sources, and how they map to score adjustments.

### Signal Hierarchy

| Rank | Signal | High Distress Threshold |
|---|---|---|
| 1 | Foreclosure notices filed | ≥ 1 |
| 2 | Loan delinquency | > 90 days |
| 3 | Maturity wall | ≤ 6 months |
| 4 | DSCR | < 0.80 |
| 5 | Weighted portfolio vacancy | > 30% |
| 6 | Negative cash flow streak | ≥ 6 consecutive months |

### Boost Table

| Distress Score | Boost | Final Score (base 50) |
|---|---|---|
| 90–100 | +36 to +40 | 86–90 |
| 70–89 | +28 to +36 | 78–86 |
| 50–69 | +20 to +28 | 70–78 |
| 30–49 | +12 to +20 | 62–70 |
| 0–29 | 0 to +12 | 50–62 |

### Current Distressed Portfolio Register

| ID | Owner | Score | Foreclosures | Delinquency | DSCR | Maturity | Final Score |
|---|---|---|---|---|---|---|---|
| DP-001 | Crestline Capital Holdings LLC | 84 | 2 | 97 days | 0.71 | 4 mo | **84** |
| DP-002 | Harmon & Weiss Property Partners | 71 | 0 | 41 days | 0.88 | 9 mo | **78** |
| DP-003 | Sunridge Development & Rentals Inc | 91 | 3 | 148 days | 0.58 | 1 mo | **86** |
| DP-004 | Trevino Asset Management Group | 55 | 0 | 0 days | 1.04 | 14 mo | **72** |

**Source file:** `data/portfolio-distress/DISTRESSED_PORTFOLIOS.json`

### Live Engine Output (2026-05-10)

```
AUTO-DP-003  |  Sunridge Development & Rentals Inc
Side: acquisition     Score:  86/100  [HIGH PRIORITY]
HIGH OPPORTUNITY — seller portfolio distress is severe (score 91/100).
Prioritise outreach and structure for speed.
Foreclosure filed on flagship Tempe asset — auction scheduled Q3 2026

  [Evidence — DISTRESSED_PORTFOLIOS / DP-003]
    · distress_score: 91
    · weighted_vacancy: 37%
    · DSCR: 0.58
    · delinquency_days: 148
    · foreclosure_notices: 3
    · maturity_wall_months: 1
    · intel_date: 2026-05-01

AUTO-DP-001  |  Crestline Capital Holdings LLC
Side: acquisition     Score:  84/100  [HIGH PRIORITY]
  · distress_score: 84  · DSCR: 0.71  · delinquency_days: 97
  · foreclosure_notices: 2  · maturity_wall_months: 4

AUTO-DP-002  |  Harmon & Weiss Property Partners
Side: acquisition     Score:  78/100  [ELEVATED]
  · distress_score: 71  · weighted_vacancy: 57%  · maturity_wall_months: 9

AUTO-DP-004  |  Trevino Asset Management Group
Side: acquisition     Score:  72/100  [ELEVATED]
  · distress_score: 55  · DSCR: 1.04  · maturity_wall_months: 14
```

### Evidence Preservation

Every scored output includes a `SourceEvidence` block tracing each signal to its origin:

```python
SourceEvidence(
    dataset="DISTRESSED_PORTFOLIOS",
    record_id="DP-003",
    signals=[
        "distress_score: 91",
        "weighted_vacancy: 37%",
        "DSCR: 0.58",
        "delinquency_days: 148",
        "foreclosure_notices: 3",
        "maturity_wall_months: 1",
    ],
    raw_score=91,
    intel_date="2026-05-01",
)
```

Source chains for each record are maintained in the JSON files under `source_evidence`, including:
- County recorder filing numbers
- Lender notice dates and parties
- Data source attribution
- Intel date (date intelligence was confirmed or last verified)

---

## Overleveraged Buyers — Live Output

```
AUTO-OB-001  |  Pinnacle Equity Acquisitions LLC
Score:  11/100  [DEPRIORITISE]  — leverage_score 87, LTV 84%, 4 escrow failures

AUTO-OB-002  |  Desert Ridge Capital Partners
Score:  14/100  [DEPRIORITISE]  — leverage_score 79, LTV 79%, SEC inquiry active

AUTO-OB-003  |  Marcus Edgeworth (individual investor)
Score:  23/100  [DEPRIORITISE]  — leverage_score 61, personal guarantee called

AUTO-OB-004  |  Ironwood Realty Fund III
Score:  33/100  [STANDARD]      — leverage_score 38, 0 escrow failures, clean credit
```

**Source file:** `data/portfolio-distress/OVERLEVERAGED_BUYERS.json`

---

## Stalled Builders — Live Output

```
AUTO-SB-001  |  Vanguard Southwest Constructors LLC
Score:   0/100  — RECLASSIFY AS SELLER (stall score 89, draw freeze, 6 mechanic liens)

AUTO-SB-002  |  Castellan Urban Development Inc
Score:   0/100  — RECLASSIFY AS SELLER (stall score 73, equity LP pulled, $5.2M cost gap)

AUTO-SB-003  |  Ridgeback Homes Arizona LLC
Score:   0/100  — RECLASSIFY AS SELLER (stall score 44, cautious_seller, bulk-lot sale open)
```

**Source file:** `data/portfolio-distress/STALLED_BUILDERS.json`

---

## Data Files

| File | Purpose |
|---|---|
| `data/portfolio-distress/DISTRESSED_PORTFOLIOS.json` | Portfolio owners with active distress signals |
| `data/portfolio-distress/OVERLEVERAGED_BUYERS.json` | Buyers with leverage metrics exceeding safe thresholds |
| `data/portfolio-distress/STALLED_BUILDERS.json` | Builders with materially stalled projects |
| `agents/deal-scoring-engine/run.py` | Python scoring agent — single entry point |

---

## Usage

```bash
# Standard run
python3 agents/deal-scoring-engine/run.py

# With evidence detail
python3 agents/deal-scoring-engine/run.py --verbose

# JSON output (pipe to jq, file, etc.)
python3 agents/deal-scoring-engine/run.py --json
```

```python
from agents.deal_scoring_engine.run import score_deal, score_all_distressed_portfolios

result = score_deal(
    deal_id="ACQ-2026-041",
    deal_side="acquisition",
    counterparty_id="DP-003",
    counterparty_name="Sunridge Development & Rentals Inc",
)
# result.composite_score  → 86
# result.recommendation   → "HIGH OPPORTUNITY — ..."
# result.seller_opportunity.evidence.signals  → ["distress_score: 91", ...]
```
