# Deal Scorecard

Reference guide for how deal scores are computed and adjusted by the `deal-scoring-engine`.

---

## Scoring Overview

All deals are scored 0–100. A base score of 50 is assumed unless overridden by the caller. Distress signals, leverage data, and builder stall status adjust the score up or down from that base.

| Score Band | Interpretation |
|---|---|
| 80–100 | High priority — act quickly |
| 65–79 | Elevated — engage with urgency |
| 50–64 | Standard — normal underwriting cadence |
| 35–49 | Cautious — additional diligence required |
| 0–34 | Deprioritise or disqualify |

---

## Scoring Modules

### 1. Seller-Side Opportunity (`scoreSellerOpportunity`)

Applied when `deal_side` is `acquisition` or `land`.

Checks the counterparty against `DISTRESSED_PORTFOLIOS.json`. If a match is found, a distress boost is added to the base score:

```
distress_boost = round((distress_score / 100) × 40)
final_score    = min(100, base_score + distress_boost)
```

A portfolio `distress_score` of 91 produces a +36 boost on a base of 50 → final score 86.

**Key distress indicators used:**
- Loan delinquency days
- Weighted portfolio vacancy rate
- Debt service coverage ratio (DSCR)
- Maturity wall (months to loan maturity)
- Foreclosure notices filed
- Consecutive months of negative cash flow

---

### 2. Buyer Priority (`scoreBuyerPriority`)

Applied when `deal_side` is `disposition`.

Checks the counterparty against `OVERLEVERAGED_BUYERS.json`. If matched, a leverage penalty is subtracted:

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

**Key leverage indicators used:**
- Portfolio LTV
- Debt-to-equity ratio
- Interest coverage ratio
- Loans currently in extension
- Escrow failures in past 12 months
- Active credit events

---

### 3. Builder Role Classification (`classifyBuilderRole`)

Applied to any counterparty matched in `STALLED_BUILDERS.json`, regardless of deal side.

Stalled builders are **reclassified as sellers**, not buyers. A builder's `role_classification` field drives this:

| Classification | Qualified as Buyer | Score Treatment |
|---|---|---|
| `motivated_seller` | No | Composite score forced to 0; seller outreach recommended |
| `cautious_seller` | No | Composite score forced to 0; evaluate carefully as seller lead |
| `qualified_buyer` | Yes | Normal buyer scoring applies |

**Key stall indicators used:**
- Stall score (0–100)
- Months since meaningful construction progress
- Construction loan status (draw freeze, default, not yet closed)
- Mechanic liens filed and claimants
- Estimated completion cost gap

---

## Portfolio Distress Signals

Portfolio distress is the primary upward pressure on seller-side opportunity scores. This section documents the signals, their sources, and how they translate into score adjustments.

### Signal Hierarchy

Signals are ranked by urgency. Higher-ranked signals carry more weight in the `distress_score` (computed externally and stored in `DISTRESSED_PORTFOLIOS.json`).

| Rank | Signal | Threshold for High Distress |
|---|---|---|
| 1 | Foreclosure notices filed | ≥ 1 |
| 2 | Loan delinquency | > 90 days |
| 3 | Maturity wall | ≤ 6 months |
| 4 | DSCR | < 0.80 |
| 5 | Weighted vacancy rate | > 30% |
| 6 | Negative cash flow streak | ≥ 6 consecutive months |

### Score Boost Table

| Distress Score | Boost Added | Effective Final Score (base 50) |
|---|---|---|
| 90–100 | +36 to +40 | 86–90 |
| 70–89 | +28 to +36 | 78–86 |
| 50–69 | +20 to +28 | 70–78 |
| 30–49 | +12 to +20 | 62–70 |
| 0–29 | 0 to +12 | 50–62 |

### Current Distressed Portfolio Register

| ID | Owner | Distress Score | Foreclosures | Delinquency (days) | DSCR | Maturity (mo) |
|---|---|---|---|---|---|---|
| DP-001 | Crestline Capital Holdings LLC | 84 | 2 | 97 | 0.71 | 4 |
| DP-002 | Harmon & Weiss Property Partners | 71 | 0 | 41 | 0.88 | 9 |
| DP-003 | Sunridge Development & Rentals Inc | 91 | 3 | 148 | 0.58 | 1 |
| DP-004 | Trevino Asset Management Group | 55 | 0 | 0 | 1.04 | 14 |

**Source:** `data/DISTRESSED_PORTFOLIOS.json` — Maricopa County Recorder, CoStar, lender notices, insider broker network.

### Score Examples

**DP-003 — Sunridge Development & Rentals Inc (score 91)**
- Foreclosure filed on flagship Tempe asset (214 units); auction scheduled Q3 2026
- 3 NODs across portfolio
- DSCR of 0.58 — deeply negative cash flow for 13 consecutive months
- Loan maturity in 1 month; bridge refi rejected by 2 lenders
- Score boost: +36 → final score 86 on base 50
- Recommendation: HIGH OPPORTUNITY — prioritise outreach, structure for speed and certainty of close

**DP-001 — Crestline Capital Holdings LLC (score 84)**
- 2 foreclosure notices; NOD on Meridian Blvd asset
- 97-day delinquency; DSCR 0.71
- LP redemptions creating liquidity pressure alongside lender action
- Score boost: +34 → final score 84 on base 50
- Recommendation: HIGH OPPORTUNITY — motivated by LP and lender pressure simultaneously

**DP-002 — Harmon & Weiss Property Partners (score 71)**
- Anchor tenant vacated Scottsdale retail Jan 2026; 57% weighted vacancy
- Principals approaching retirement — succession gap adds urgency
- Western Alliance forbearance request in play
- Score boost: +28 → final score 78 on base 50
- Recommendation: ELEVATED OPPORTUNITY — engage with relationship-first approach

**DP-004 — Trevino Asset Management Group (score 55)**
- No foreclosures, current on debt — but land carry costs mounting
- Entitlement timeline extended 18 months; office losing tenants
- Score boost: +22 → final score 72 on base 50
- Recommendation: MODERATE OPPORTUNITY — monitor and maintain contact; not yet urgency-driven

### Evidence Preservation

Every score output includes a `source_evidence` block tracing the signal back to its origin:

```ts
{
  dataset: 'DISTRESSED_PORTFOLIOS',
  record_id: 'DP-003',
  signals: [
    'distress_score: 91',
    'weighted_vacancy: 37%',
    'DSCR: 0.58',
    'delinquency_days: 148',
    'foreclosure_notices: 3',
    'maturity_wall_months: 1'
  ],
  raw_score: 91,
  intel_date: '2026-05-01'
}
```

Source chains for each portfolio are maintained in `DISTRESSED_PORTFOLIOS.json` under `source_evidence`, including:
- County recorder filing numbers
- Lender notice dates and parties
- Data source attribution
- Intel date (date intelligence was confirmed)

---

## Data Files

| File | Purpose | Located |
|---|---|---|
| `data/DISTRESSED_PORTFOLIOS.json` | Portfolio owners with active distress signals | `/data/` |
| `data/OVERLEVERAGED_BUYERS.json` | Buyers with leverage metrics exceeding safe thresholds | `/data/` |
| `data/STALLED_BUILDERS.json` | Builders with materially stalled projects | `/data/` |
| `src/lib/deal-scoring-engine.ts` | Scoring engine integrating all three datasets | `/src/lib/` |

---

## Usage

```ts
import { scoreDeal, scoreAllDistressedPortfolios } from '@/lib/deal-scoring-engine';

// Score a specific acquisition target
const result = scoreDeal({
  deal_id: 'ACQ-2026-041',
  deal_side: 'acquisition',
  counterparty_id: 'DP-003',
  counterparty_name: 'Sunridge Development & Rentals Inc',
  base_score: 50,
});

// result.composite_score → 86
// result.recommendation  → 'HIGH OPPORTUNITY — ...'
// result.seller_opportunity.evidence → { dataset: 'DISTRESSED_PORTFOLIOS', ... }

// Batch-score all distressed portfolio owners
const allScores = scoreAllDistressedPortfolios();
```
