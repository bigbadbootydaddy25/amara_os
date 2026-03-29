# Land LDP Underwriting

## Rule
Max Land Value = Gross − Dev Cost − Builder Profit.
Never offer above Max Land Value.
Minimum spread $100,000. Priority deals $1,000,000+.

---

## The 7-Step Formula

```
Step 1:  Lots           = Acres × Density
Step 2:  Lot Value      = Median Home Price × 0.22–0.25
Step 3:  Gross Value    = Lots × Lot Value
Step 4:  Dev Cost       = Lots × $60,000  (adjust by market)
Step 5:  Builder Profit = Gross Value × 0.15
Step 6:  Max Land Value = Gross − Dev Cost − Builder Profit
Step 7:  Spread         = Max Land Value − Asking Price
```

---

## Default Inputs

| Input | Default | When to Adjust |
|-------|---------|---------------|
| Density | 3.5 lots/acre | Lower for rural (1–2), higher for urban infill (5–8) |
| Lot multiplier | 0.23 | 0.25 in hot markets, 0.20 in soft or no builder activity |
| Dev cost/lot | $60,000 | $45k full utilities, $80k+ no utilities / tough terrain |
| Builder profit | 15% | Fixed — do not reduce |

---

## Spread Tiers

| Spread | Decision |
|--------|----------|
| < $100,000 | Dead — walk away |
| $100,000 – $249,999 | Minimum viable — proceed cautiously |
| $250,000 – $999,999 | Preferred — pursue actively |
| $1,000,000+ | Priority — move fast |

---

## Fast Example

**4.2 acres, suburban Phoenix, asking $90,000, median new home $365,000**

```
Lots:         4.2 × 3.5 = 14 lots
Lot Value:    $365,000 × 0.23 = $83,950
Gross:        14 × $83,950 = $1,175,300
Dev Cost:     14 × $60,000 = $840,000
Profit:       $1,175,300 × 0.15 = $176,295
Max Land:     $1,175,300 − $840,000 − $176,295 = $159,005
Spread:       $159,005 − $90,000 = $69,005
```

**Result: $69,005 — DEAD. Below $100k minimum.**

---

## Dev Cost Adjustments

| Condition | Adjustment |
|-----------|-----------|
| Full utilities to site | −$10,000–$15,000/lot |
| Utilities nearby, not to site | Baseline $60,000 |
| No utilities, rural | +$15,000–$40,000/lot |
| Difficult terrain | +$10,000–$20,000/lot |
| Already entitled / approved | −$5,000–$10,000/lot |

---

## Red Flags

- No builder activity confirmed (see `playbooks/comps/land_comp_logic.md`)
- Flood zone covering significant acreage — reduce buildable acres in Step 1
- Seller anchored to residential land comps — land math doesn't support those prices
- Utility extension cost unknown — don't proceed without estimate from engineer

---

## After LDP

If spread is viable:
1. Confirm land buyer from `buyers/` vault
2. Create `land/LAND-XXXX.md` with all 7 steps documented
3. Log observation if market data revealed something new

CLI shortcut:
```
python amara.py ldp --acres 4.2 --median-home-price 365000 --asking-price 90000
```
