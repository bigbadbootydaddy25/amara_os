# SFR Fast Math

## Rule
One formula. One decision. Under 60 seconds.
If the math doesn't work at first pass, the deal is dead or needs negotiation. Do not force it.

---

## The Formula

```
MAO = Buyer Price − Repairs − Assignment Fee
```

**Minimums (non-negotiable):**
- Assignment fee floor: $10,000
- Assignment fee target: $15,000

**Never use 70% ARV. Always use buyer price from comp read.**

---

## Fast Math Table

Use the table to get an instant MAO estimate. Then verify with exact numbers.

| Buyer Price | Repairs | Target Fee | MAO |
|------------|---------|-----------|-----|
| $100,000 | $20,000 | $15,000 | $65,000 |
| $120,000 | $25,000 | $15,000 | $80,000 |
| $140,000 | $30,000 | $15,000 | $95,000 |
| $160,000 | $30,000 | $15,000 | $115,000 |
| $180,000 | $35,000 | $15,000 | $130,000 |
| $200,000 | $35,000 | $15,000 | $150,000 |
| $220,000 | $40,000 | $15,000 | $165,000 |
| $250,000 | $45,000 | $15,000 | $190,000 |
| $280,000 | $50,000 | $15,000 | $215,000 |
| $300,000 | $55,000 | $15,000 | $230,000 |

*Use as a reference. Always run exact numbers before sending offer.*

---

## Repair Estimation — Fast Track

Three inputs: condition, sqft, market.

| Condition | Scope | $/sqft |
|-----------|-------|--------|
| Light | Cosmetic — paint, floors, fixtures | $15–$20 |
| Medium | Kitchen, baths, systems | $30–$45 |
| Heavy | Full gut + structural | $60–$90 |

**Phoenix market:** Add 18% to all repair estimates (labor premium).
**Repair rule:** Always estimate at the high end of the range. Surprises go up, not down.

**Fast estimate:** Sqft × $/sqft = repairs. Round up to nearest $5,000.

---

## 60-Second Decision Tree

```
1. Do I have a confirmed buyer for this ZIP?
   NO → Stop. Find buyer first.
   YES → Continue.

2. Buyer price from comp read?
   Set using playbooks/comps/sfr_comp_reading.md

3. Estimate repairs (fast track above).

4. MAO = Buyer Price - Repairs - $15,000

5. Is seller asking ≤ MAO?
   YES → Deal works. Confirm with buyer. Send offer.
   NO  → Gap = Seller Ask - MAO.
         Can I negotiate seller down to MAO?
         YES → Negotiate.
         NO  → Dead. Move on.

6. Fee check:
   Fee = Buyer Price - Repairs - Contract Price
   Fee ≥ $15,000? → Strong deal.
   Fee $10,000–$14,999? → Acceptable minimum. Proceed.
   Fee < $10,000? → Do not proceed.
```

---

## Output

After running fast math, the deal file needs:

```
## MAO
Buyer Price:   $________
Repairs:     - $________
Fee (target):- $15,000
─────────────────────
MAO:           $________
```

Record in `deals/DEAL-XXXX.md`.

---

## When to Stop Fast Math and Go Deep

Only escalate to full analysis if:
- Assignment fee is between $10k–$15k (acceptable but tight — verify repair estimate)
- Seller is at MAO but repair estimate has uncertainty (old home, unseen interior)
- Multiple buyers want the deal (optimize fee, not just viability)

Otherwise: fast math is sufficient. Don't add steps that don't change the decision.
