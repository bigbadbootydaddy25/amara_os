# Playbook: Land LDP Underwriting

## Purpose
Determine Max Land Value and spread on residential land development plays.
Used for raw land where the exit is selling lots to a builder or developing finished lots.

---

## Core Rules

- Minimum spread: $100,000 — no exceptions
- Preferred spread: $250,000+
- Priority deals: $1,000,000+ spread
- Do NOT pursue without a confirmed land/developer buyer first
- Spread = Max Land Value − Asking Price. Never offer above Max Land Value.

---

## The Formula (All 7 Steps)

### Step 1 — Estimate Lots

```
Lots = Acres × Density
```

**Typical density by use type:**

| Market Type | Density (lots/acre) |
|-------------|-------------------|
| Suburban SFR | 3–4 lots/acre |
| Urban infill | 4–6 lots/acre |
| Rural / low-density | 1–2 lots/acre |
| Town homes / attached | 6–10 lots/acre |

Default if unknown: **3.5 lots/acre**

> Confirm with a local engineer or zoning office for entitled land. Use conservative end for unentitled.

---

### Step 2 — Finished Lot Value

```
Lot Value = Median Home Price × 0.22 to 0.25
```

**Why 22–25%?**
Builders typically allocate 20–25% of the finished home sale price to lot cost.
Use 0.22 for conservative markets, 0.25 for strong/hot markets.

**Example:**
- Median home price in ZIP: $380,000
- Lot Value: $380,000 × 0.23 = **$87,400 per lot**

> Pull median home price from Zillow, Redfin, or MLS for the target ZIP. Use sold data, not listing price.

---

### Step 3 — Gross Value

```
Gross Value = Lots × Lot Value
```

**Example:**
- 12 lots × $87,400 = **$1,048,800**

This is the total value of the finished lots before development costs and profit.

---

### Step 4 — Development Cost

```
Development Cost = Lots × $60,000
```

**$60,000/lot is the baseline. Adjust by market:**

| Condition | Adjustment |
|-----------|-----------|
| Full utilities to site | $45,000–$55,000/lot |
| Utilities nearby but not to site | $55,000–$70,000/lot |
| No utilities, rural | $70,000–$100,000/lot |
| Challenging topography | +$10,000–$20,000/lot |
| Entitled/approved | -$5,000–$10,000/lot (saves entitlement cost) |

> Always verify development cost estimate with a civil engineer or local developer on larger deals.

---

### Step 5 — Builder Profit

```
Builder Profit = Gross Value × 0.15
```

Builders typically require a minimum 15% profit margin on a land development deal.
This is their minimum — do not reduce it. Reducing builder margin kills the deal.

**Example:**
- $1,048,800 × 0.15 = **$157,320**

---

### Step 6 — Max Land Value

```
Max Land Value = Gross Value − Development Cost − Builder Profit
```

**Full Example:**
```
Gross Value:             $1,048,800
Development Cost:      -   $720,000  (12 lots × $60,000)
Builder Profit:        -   $157,320  (15%)
──────────────────────────────────────
Max Land Value:           $171,480
```

This is the maximum a rational developer will pay for the raw land.
**Never offer above Max Land Value.**

---

### Step 7 — Spread

```
Spread = Max Land Value − Asking Price
```

**Example:**
- Max Land Value: $171,480
- Seller Asking: $60,000
- Spread: **$111,480** ✓ (above $100,000 minimum)

---

## Spread Decision Table

| Spread | Decision |
|--------|----------|
| < $100,000 | Dead — do not pursue |
| $100,000 – $249,999 | Viable minimum — proceed cautiously |
| $250,000 – $999,999 | Preferred — pursue actively |
| $1,000,000+ | Priority deal — move fast |

---

## Full Worked Example

**Property:** 4.2 acres, suburban market, no entitlements
**Median home price (ZIP):** $340,000
**Asking price:** $85,000

```
Step 1 — Lots:        4.2 acres × 3.5 = 14.7 → 14 lots (round down)
Step 2 — Lot Value:   $340,000 × 0.23 = $78,200/lot
Step 3 — Gross Value: 14 × $78,200 = $1,094,800
Step 4 — Dev Cost:    14 × $60,000 = $840,000
Step 5 — Builder Profit: $1,094,800 × 0.15 = $164,220
Step 6 — Max Land Value: $1,094,800 - $840,000 - $164,220 = $90,580
Step 7 — Spread:      $90,580 - $85,000 = $5,580
```

**Result: $5,580 spread — DEAD. Walk away.**

Seller needs to be at ~$0 for minimum spread, or the deal needs 5+ acres to generate lot count.

---

## Red Flags

| Flag | Action |
|------|--------|
| No zoning confirmation | Assume lowest density until verified |
| Flood zone / wetlands | Reduce buildable acres before Step 1 |
| No road access | Add road cost to development cost estimate |
| Seller anchored to retail comp prices | Educate or walk — residential lot math doesn't support retail land pricing |
| Entitlements uncertain | Use unentitled density (conservative) and note risk |
| Median home price hard to establish | Do not proceed — data is the foundation |

---

## Vault Integration

After underwriting a land deal:
- Record all 7 steps in `land/LAND-XXXX.md` under `## Spread Calculation`
- Note density assumption used and source
- Note development cost adjustment if market required it
- If Max Land Value and spread are confirmed viable → match buyer → then and only then create the deal file
