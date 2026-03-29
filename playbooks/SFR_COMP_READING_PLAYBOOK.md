# Playbook: SFR Comp Reading

## Purpose
Determine the REAL buyer price using actual investor behavior —
not retail listings, not Zestimates, not the highest comp.

---

## Core Rule

> The buyer price is what a real investor will actually pay for the property as-is.
> It is derived from what investors have recently paid — not what retail buyers paid for renovated homes.

---

## Step 1 — Pull Comps

**Sources (in order of preference):**
1. Zillow — Sold tab (filter: sold, last 6 months)
2. Redfin — Sold homes (same filter)
3. PropStream — Transaction history by ZIP (use `playbooks/PROPSTREAM_PLAYBOOK.md`)

**Filter criteria:**
- Same ZIP code (or immediate adjacent ZIPs if volume is low)
- Sold in last 6 months — extend to 12 months max if fewer than 5 results
- Sqft: within ±20% of subject property
- Same bed/bath count (or within 1 bed)

---

## Step 2 — Filter Out

Remove these from your comp set before calculating anything:

| Remove | Reason |
|--------|--------|
| Perfect condition / fully renovated listings | Retail buyer, not investor — inflates ARV |
| New construction | Different cost basis — not comparable |
| Outliers (far above or below cluster) | Distorts average |
| Different neighborhoods / school districts | Market conditions don't transfer |
| MLS listings that sold above list price | Bidding war anomaly |

**What remains = your working comp set.**

---

## Step 3 — Identify Investor Comps

Within your working comp set, look for comps that reflect investor exits:

**Signals a comp is an investor comp:**
- Sold by an LLC or investor entity (check public records or PropStream buyer name)
- Property was recently renovated before sale (DOM was short, price jumped from prior sale)
- Repeat buyer name on the deed — known operator in that ZIP
- Similar rehab style to subject (comparable scope of work)
- Sold AS-IS or "cash only" in listing remarks

**These comps are the most accurate reflection of what your buyer will ultimately sell for.**
Use them to anchor your ARV — but remember: your buyer is buying at a discount to ARV.

---

## Step 4 — Determine Buyer Price

**Do NOT use the highest comp.**
**Do NOT use the retail ARV as the buyer price.**

> Buyer price = what an investor will pay as-is, before their repairs.

**Formula:**
1. Take the top 3–5 investor-aligned comps (after-repair sales by flippers in that ZIP)
2. Average them → this is your ARV estimate
3. Buyer price is NOT the ARV — buyer price is what they'll pay to acquire in current condition

**To find buyer price:**
- Talk to your matched buyer (ask their current buy price in that ZIP)
- Cross-reference with their buy box in `buyers/BUY-XXXX.md`
- Use recent cash transaction data from PropStream as validation

**Never calculate MAO using an ARV you haven't verified with at least 3 comps.**

---

## Step 5 — Speed Rule

**Decision must be made in under 60 seconds.**

Once comps are pulled and filtered:
- Average the top 3–5 clean comps
- Check against buyer's stated buy price range
- Go / no-go

> Speed > perfection. A good comp read in 60 seconds beats a perfect comp read in 2 hours.
> If you're spending more than 10 minutes on comps for a quick screen, you're overanalyzing.

---

## MAO After Comp Read

Once buyer price is confirmed, run MAO:

```
Buyer Price (from comp read + buyer confirmation):  $
Repairs (conservative):                           - $
Target Assignment Fee:                            - $15,000
──────────────────────────────────────────────────────────
MAO:                                                $
```

See `playbooks/SFR_PLAYBOOK.md` for full deal workflow.

---

## Red Flags in Comp Reads

| Flag | Action |
|------|--------|
| All comps are retail / move-in ready | You're reading ARV, not buyer price — find investor comps |
| Comp spread is too wide (>$50k range) | Market is inconsistent — use only tightest cluster |
| No comps within 6 months | Slow market — extend to 12 months, note risk |
| Only 1–2 comps available | Thin data — confirm with buyer directly before relying on comps |
| Subject property is unique (odd sqft, weird layout) | Manual buyer confirmation required |

---

## Vault Integration

After a comp read:
- Record buyer price in the deal file (`deals/DEAL-XXXX.md`) under `## Valuation`
- List your top 3 comps with address, price, sqft, and sale date
- If comp read revealed something about the market, log an observation in `observations/`
