# Deal Scorecard

**Agent:** `agents/deal-scoring-engine/run.py`
**Run date:** 2026-05-10
**Pipeline deals scored:** 30

---

## Run Summary

| Metric | Count |
|---|---|
| Total deals scored | 30 |
| Distress-boosted (seller) | 12 |
| Leverage-penalised (buyer) | 6 |
| Builders reclassified as sellers | 4 |
| HIGH PRIORITY (≥80) | 8 |
| ELEVATED (65–79) | 4 |
| DEPRIORITISE (<35) | 11 |

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

| Deal | Owner | Distress Score | Final Score | Signal |
|---|---|---|---|---|
| D-0001 | Sunridge Development & Rentals Inc | 91/100 | **86/100** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 91/100). Prioritis |
| D-0006 | Sunridge Development & Rentals Inc | 91/100 | **86/100** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 91/100). Prioritis |
| D-0007 | Sunridge Development & Rentals Inc | 91/100 | **86/100** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 91/100). Prioritis |
| D-0028 | Sunridge Development & Rentals Inc | 91/100 | **86/100** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 91/100). Prioritis |
| D-0030 | Sunridge Development & Rentals Inc | 91/100 | **86/100** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 91/100). Prioritis |
| D-0002 | Crestline Capital Holdings LLC | 84/100 | **84/100** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 84/100). Prioritis |
| D-0003 | Crestline Capital Holdings LLC | 84/100 | **82/100** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 84/100). Prioritis |
| D-0025 | Crestline Capital Holdings LLC | 84/100 | **84/100** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 84/100). Prioritis |
| D-0004 | Harmon & Weiss Property Partners | 71/100 | **78/100** | ELEVATED OPPORTUNITY — meaningful distress detected (score 71/100). Engage with  |
| D-0008 | Harmon & Weiss Property Partners | 71/100 | **75/100** | ELEVATED OPPORTUNITY — meaningful distress detected (score 71/100). Engage with  |
| D-0005 | Trevino Asset Management Group | 55/100 | **72/100** | ELEVATED OPPORTUNITY — meaningful distress detected (score 55/100). Engage with  |
| D-0020 | Trevino Asset Management Group | 55/100 | **72/100** | ELEVATED OPPORTUNITY — meaningful distress detected (score 55/100). Engage with  |


---

## Overleveraged Buyers — Dispo Downgrades

Buyer names are matched against `data/portfolio-distress/OVERLEVERAGED_BUYERS.json`. Leverage penalty applied:

```
leverage_penalty = round((leverage_score / 100) × 45)
final_score      = max(0, base_score - leverage_penalty)
```

### Overleveraged Buyers Matched This Run

| Deal | Buyer | Leverage Score | Final Score | Priority |
|---|---|---|---|---|
| D-0011 | Pinnacle Equity Acquisitions LLC | 87/100 | **11/100** | `disqualified` |
| D-0015 | Pinnacle Equity Acquisitions LLC | 87/100 | **16/100** | `disqualified` |
| D-0012 | Desert Ridge Capital Partners | 79/100 | **14/100** | `downgraded` |
| D-0023 | Desert Ridge Capital Partners | 79/100 | **16/100** | `downgraded` |
| D-0013 | Marcus Edgeworth (individual investor) | 61/100 | **23/100** | `downgraded` |
| D-0029 | Marcus Edgeworth (individual investor) | 61/100 | **21/100** | `downgraded` |


---

## Stalled Builders — Role Reclassification

Builder names are matched against `data/portfolio-distress/STALLED_BUILDERS.json`. Stalled builders are treated as motivated sellers; composite score is forced to 0 on the buyer side.

### Builders Reclassified This Run

| Deal | Builder | Stall Score | Classification |
|---|---|---|---|
| D-0017 | Vanguard Southwest Constructors LLC | 89/100 | `motivated_seller` |
| D-0024 | Vanguard Southwest Constructors LLC | 89/100 | `motivated_seller` |
| D-0018 | Castellan Urban Development Inc | 73/100 | `motivated_seller` |
| D-0019 | Ridgeback Homes Arizona LLC | 44/100 | `cautious_seller` |


---

## HIGH PRIORITY Deals (score ≥ 80)

| Deal | Counterparty | Side | Score | Recommendation |
|---|---|---|---|---|
| D-0001 | Sunridge Development & Rentals Inc | acquisition | **86** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 91/100). Prioritise outreach |
| D-0006 | Sunridge Development & Rentals Inc | acquisition | **86** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 91/100). Prioritise outreach |
| D-0007 | Sunridge Development & Rentals Inc | acquisition | **86** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 91/100). Prioritise outreach |
| D-0028 | Sunridge Development & Rentals Inc | acquisition | **86** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 91/100). Prioritise outreach |
| D-0030 | Sunridge Development & Rentals Inc | land | **86** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 91/100). Prioritise outreach |
| D-0002 | Crestline Capital Holdings LLC | acquisition | **84** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 84/100). Prioritise outreach |
| D-0025 | Crestline Capital Holdings LLC | jv | **84** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 84/100). Prioritise outreach |
| D-0003 | Crestline Capital Holdings LLC | acquisition | **82** | HIGH OPPORTUNITY — seller portfolio distress is severe (score 84/100). Prioritise outreach |


---

## Source Files

| File | Purpose |
|---|---|
| `data/deals.json` | Active deal pipeline |
| `data/portfolio-distress/DISTRESSED_PORTFOLIOS.json` | Distressed portfolio owners |
| `data/portfolio-distress/OVERLEVERAGED_BUYERS.json` | Overleveraged buyers |
| `data/portfolio-distress/STALLED_BUILDERS.json` | Stalled builders |
| `agents/deal-scoring-engine/run.py` | Scoring agent |
