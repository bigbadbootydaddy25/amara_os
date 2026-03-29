# SFR Comp Reading

## Rule
Speed > perfection. Decision in under 60 seconds.
Do not overanalyze. Pull comps, identify investor exits, set buyer price, move.

---

## Step 1 — Pull Comps

Sources (in order):
1. Zillow — Sold tab
2. Redfin — Sold homes
3. PropStream — Transaction history by ZIP

Filters:
- Same ZIP (adjacent ZIP only if fewer than 3 results)
- Last 6 months (extend to 12 max if needed)
- Sqft ±20% of subject
- Same bed/bath (±1 bed acceptable)

---

## Step 2 — Strip Out Noise

Remove immediately:
- Fully renovated / move-in ready retail sales
- New construction
- Outliers (>$30k above or below the cluster)
- Different neighborhood or school district
- Bidding war sales (sold >5% over list)

What remains = working comp set.

---

## Step 3 — Find Investor Exits

Within the working set, flag comps that are investor sales:
- Sold by LLC or known investor entity
- Short hold period (bought low, sold higher after rehab)
- Similar rehab scope to subject property
- Repeat buyer name on deed

These comps anchor your ARV. They show what the exit actually looks like.

---

## Step 4 — Set Buyer Price

> Buyer price ≠ ARV. Buyer price = what an investor pays as-is today.

Process:
1. Average top 3–5 clean comps → ARV
2. Check matched buyer's buy box in `buyers/BUY-XXXX.md`
3. Confirm buyer price is within their stated range for this ZIP
4. If no buyer on file for this ZIP → stop, find buyer first

Buyer price is confirmed when:
- It matches or is below the buyer's max for this corridor
- ARV supports the buyer's flip margin

---

## Step 5 — 60-Second Decision

| Time | Action |
|------|--------|
| 0–20s | Pull comps, apply filters |
| 20–40s | Strip noise, identify investor exits |
| 40–55s | Average top comps, check buyer buy box |
| 55–60s | Go / No-Go |

**Go** → pass buyer price to `playbooks/underwriting/sfr_fast_math.md`
**No-Go** → log reason, move on

---

## Red Flags (Instant No-Go)

- All comps are retail / renovated (no investor exits visible)
- Comp spread >$50k with no clear cluster
- Fewer than 2 comps in 12 months → thin market, skip
- Subject is a unique property (odd layout, unusual sqft) → manual buyer call required
