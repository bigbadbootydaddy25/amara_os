# Deal Scorecard

**Agent:** `agents/deal-scoring-engine/run.py`
**Run:** 2026-05-10 00:32 UTC
**Report:** `agents/deal-scoring-engine/reports/20260510T003244Z/DEAL_SCORECARD.md`

---

## Run Summary

| Metric | Count |
|---|---|
| Scored deals | 11 |
| Hot deals (≥ 80) | 2 |
| Elevated (65–79) | 2 |
| Deprioritised (< 35) | 7 |
| Distress-boosted sellers | 4 |
| Leverage-penalised buyers | 3 |
| Builders reclassified as sellers | 3 |

---

## Portfolio Distress Signals

Portfolio distress boosts seller-side opportunity scores. Owner, buyer, and builder names are matched at score time against the three distress datasets in `data/portfolio-distress/`.

### Signal Hierarchy

| Rank | Signal | High Distress Threshold |
|---|---|---|
| 1 | Foreclosure notices filed | ≥ 1 |
| 2 | Loan delinquency | > 90 days |
| 3 | Maturity wall | ≤ 6 months |
| 4 | DSCR | < 0.80 |
| 5 | Weighted portfolio vacancy | > 30% |
| 6 | Negative cash flow streak | ≥ 6 consecutive months |

### Scoring Adjustments

```
# Seller boost (DISTRESSED_PORTFOLIOS)
distress_boost = round((distress_score / 100) × 40)
final_score    = min(100, base_score + distress_boost)

# Buyer penalty (OVERLEVERAGED_BUYERS)
leverage_penalty = round((leverage_score / 100) × 45)
final_score      = max(0, base_score - leverage_penalty)

# Builder reclassification (STALLED_BUILDERS)
# → composite_score forced to 0 when role != qualified_buyer
```

### Distressed Portfolio Owners Matched This Run

| Deal | Owner | Distress Score | Final Score | Signal |
|---|---|---|---|---|
| AUTO-DP-003 | Sunridge Development & Rentals Inc | 91/100 | **86/100** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 91/100). Prioritis |
| AUTO-DP-001 | Crestline Capital Holdings LLC | 84/100 | **84/100** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 84/100). Prioritis |
| AUTO-DP-002 | Harmon & Weiss Property Partners | 71/100 | **78/100** | ELEVATED OPPORTUNITY — meaningful distress detected (score 71/100). Engage with  |
| AUTO-DP-004 | Trevino Asset Management Group | 55/100 | **72/100** | ELEVATED OPPORTUNITY — meaningful distress detected (score 55/100). Engage with  |


### Overleveraged Buyers Matched This Run

| Deal | Buyer | Leverage Score | Final Score | Priority |
|---|---|---|---|---|
| AUTO-OB-001 | Pinnacle Equity Acquisitions LLC | 87/100 | **11/100** | `disqualified` |
| AUTO-OB-002 | Desert Ridge Capital Partners | 79/100 | **14/100** | `downgraded` |
| AUTO-OB-003 | Marcus Edgeworth (individual investor) | 61/100 | **23/100** | `downgraded` |


### Stalled Builders Reclassified This Run

| Deal | Builder | Stall Score | Classification |
|---|---|---|---|
| AUTO-SB-001 | Vanguard Southwest Constructors LLC | 89/100 | `motivated_seller` |
| AUTO-SB-002 | Castellan Urban Development Inc | 73/100 | `motivated_seller` |
| AUTO-SB-003 | Ridgeback Homes Arizona LLC | 44/100 | `cautious_seller` |


---

## Hot Deals — score ≥ 80

| Deal | Counterparty | Side | Score | Recommendation |
|---|---|---|---|---|
| AUTO-DP-003 | Sunridge Development & Rentals Inc | acquisition | **86** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 91/100). Prioritise outreach |
| AUTO-DP-001 | Crestline Capital Holdings LLC | acquisition | **84** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 84/100). Prioritise outreach |

---

## Source Files

| File | Purpose |
|---|---|
| `data/portfolio-distress/DISTRESSED_PORTFOLIOS.json` | Distressed portfolio owners |
| `data/portfolio-distress/OVERLEVERAGED_BUYERS.json` | Overleveraged buyers |
| `data/portfolio-distress/STALLED_BUILDERS.json` | Stalled builders |
| `agents/deal-scoring-engine/run.py` | Scoring agent |
