# Playbook: SFR Wholesale

## Deal Type
Single Family Residential (SFR) — Wholesale / Assignment

---

## Core Rules (Non-Negotiable)

1. **Buyer-first.** Confirm a buyer exists before pursuing the property.
2. **Minimum assignment fee: $10,000** — never go below.
3. **Target assignment fee: $15,000+**
4. **DO NOT use 70% ARV rule.**
5. **MAO formula:**
   ```
   MAO = Buyer Price − Repairs − Assignment Fee
   ```

---

## Step-by-Step Workflow

### Step 1 — Confirm Buyer Demand
- Search `buyers/` for active buyers matching:
  - Asset type: SFR
  - State / City / ZIP
  - Price range that fits the deal
- If no buyer exists in that corridor → do not pursue the property
- If buyer exists → note their max buy price and repair tolerance

### Step 2 — Property Intake
Gather from seller / data source:
- [ ] Address + APN
- [ ] Beds / Baths / Sqft / Year Built
- [ ] Condition (as-is / light / medium / heavy rehab)
- [ ] Seller motivation
- [ ] Seller asking price
- [ ] Seller timeline

### Step 3 — Pull ARV
- Pull 3+ comps within 0.5 miles, same bed/bath, last 6 months
- Adjust for condition, sqft, and lot
- Record ARV + comp sources in deal file
- **ARV ≠ buyer price.** Buyer price = what an investor will actually pay as-is.

### Step 4 — Estimate Repairs
Use market repair benchmarks from `markets/`:
- Light: cosmetic only (paint, floors, fixtures) — $15–$25/sqft
- Medium: kitchens, baths, systems — $30–$50/sqft
- Heavy: full gut / structural — $60–$100/sqft
- Note: always estimate conservatively (high repairs)

### Step 5 — Calculate MAO

```
Buyer Price (what investor pays):   $________
Repairs (conservative estimate):  - $________
Target Assignment Fee ($15k):     - $15,000
────────────────────────────────────────────
MAO (Max Allowable Offer):          $________
```

Run `system/mao_calculator.py` for precise calculation.

**If seller asking > MAO:**
- Negotiate down to MAO
- Never go under contract above MAO
- If seller won't budge → walk away

### Step 6 — Match Buyer
- Run buyer match using `system/buyer_matcher.py`
- Send deal to top 3–5 matched buyers
- Include:
  - Address (or blind address until interest confirmed)
  - Property details
  - ARV
  - Repairs estimate
  - Asking price / your contract price
  - Assignment fee

### Step 7 — Send Offer
- Once buyer confirmed → send seller offer at or below MAO
- Preferred: send at MAO − buffer (protect against repair surprises)
- Use a clear assignment clause in the contract

### Step 8 — Record Outcome
After closing (or deal death), create a deal result file:
- See `deal-results/TEMPLATE.md`
- Run learning protocol: `system/learning_protocol.py`

---

## Common Deal Killers (Watch For)

| Issue | Action |
|-------|--------|
| No buyer in corridor | Stop — find buyer first |
| Repairs estimated too low | Inflate by 20% buffer |
| ARV pulled from retail MLS | Adjust for investor discount |
| Seller won't meet MAO | Walk away or reassign effort |
| Assignment fee below $10k | Do not proceed |
| Title issues / liens | Investigate before going under contract |

---

## MAO Quick Reference

| Buyer Price | Repairs | Target Fee | MAO |
|------------|---------|-----------|-----|
| $200,000 | $30,000 | $15,000 | $155,000 |
| $150,000 | $20,000 | $15,000 | $115,000 |
| $100,000 | $25,000 | $15,000 | $60,000 |
| $250,000 | $40,000 | $15,000 | $195,000 |
| $300,000 | $50,000 | $15,000 | $235,000 |

*Always calculate for your specific deal. Use `mao_calculator.py`.*

---

## Vault Links
- Buyers: `buyers/`
- Deals: `deals/`
- Markets: `markets/`
- ZIP Corridors: `zip-corridors/`
- Observations: `observations/`
