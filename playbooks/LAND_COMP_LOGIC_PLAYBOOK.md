# Playbook: Land Comp Logic

## Purpose
Estimate land value without relying on traditional raw land comps.
Raw land comps are rare, stale, and often misleading.
The real signal is what builders are doing — not what raw land last sold for.

---

## Core Rule

> Land value is derived from what builders are selling finished homes for,
> not from what raw land last traded at.

Use the LDP formula (`playbooks/LAND_LDP_UNDERWRITING_PLAYBOOK.md`) anchored to
builder activity — not raw land transaction history.

---

## The 4 Signals

Read all four before drawing a conclusion. No single signal is sufficient.

### Signal 1 — Nearby Builders
**What to look for:**
- Active homebuilders (national, regional, or local) within 1–3 miles
- Builder names: D.R. Horton, Lennar, KB Home, Pulte, LGI, Taylor Morrison, local operators
- How to find: Google Maps ("new homes near [city]"), builder websites, county permit records

**What it means:**
- Builders have already validated the market — they have demand data, absorption rates, and lot cost models
- Their presence confirms that finished lots in this area have a buyer
- The closer the builder, the more directly comparable their lot pricing is to yours

**Red flag:** Builders present but pulling back (pausing phases, reducing prices) = softening market. Check timing.

---

### Signal 2 — Active Subdivisions
**What to look for:**
- Subdivisions with open phases — meaning they are actively selling lots or homes
- Construction activity visible (framing, concrete, utility work)
- New roads being cut — sign of active land development
- How to find: Google Earth time-lapse, county GIS, driving the area

**What it means:**
- Active subdivision = proven lot absorption in this sub-market
- Remaining phases being opened = developers believe demand continues
- Directly adjacent undeveloped land benefits from infrastructure spillover

**Red flag:** Subdivision started but stalled (weeds growing in partially graded lots) = demand problem or funding failure. Investigate before proceeding.

---

### Signal 3 — New Construction Prices
**What to look for:**
- What are builders selling finished homes for in this area?
- New construction price per sqft vs. existing homes
- Builder incentives (large incentives = slower absorption — note risk)
- How to find: Builder websites, Zillow new construction filter, Redfin, MLS new construction filter

**What it means:**
- New construction price is your median home price input for the LDP formula
- If builders are selling at $380k, use $380k as your median in Step 2 of LDP
- Builder pricing at premium to existing homes = strong land market
- Builder pricing at parity or discount = compressed margins — reduce lot value multiplier to 0.20–0.22

---

### Signal 4 — Expansion Direction
**What to look for:**
- Which direction is the metro growing?
- Where are new roads, highways, and infrastructure being built?
- Where are employers, warehouses, and retail expanding?
- How to find: City/county GIS, Google Maps satellite view (compare 2018 vs. today), news on major employers or infrastructure projects

**What it means:**
- Land in the path of expansion has a forward-looking premium
- Land against the expansion direction (metro is growing away from it) loses value
- Infrastructure commitment (new interchange, water/sewer extension) is the highest-confidence signal of all

**Key question:** Is this land in the path of growth, or in the wake of it?

---

## Decision Rule

If all three of the following are true → **high probability land deal**:

| Condition | Check |
|-----------|-------|
| Builder nearby (within 1–3 miles) | [ ] Yes |
| Infrastructure present (utilities, roads) | [ ] Yes |
| Expansion active (metro growing toward parcel) | [ ] Yes |

**All three checked:** Run LDP underwriting. If spread ≥ $100,000, pursue.
**Two of three:** Run LDP conservatively (lower density, lower lot multiplier). Require spread ≥ $250,000.
**One or zero:** Do not pursue. Insufficient demand signals.

---

## How to Use This With the LDP Formula

1. Run Signals 1–4 to confirm the market
2. Pull new construction sale prices → use as `median_home_price` in LDP
3. Confirm density assumption from local zoning
4. Run `python amara.py ldp --acres X --median-home-price X --asking-price X`
5. If spread meets threshold → confirm buyer/developer → create deal file

---

## What Bad Land Comp Logic Looks Like

| Mistake | Why It's Wrong |
|---------|---------------|
| "The lot next door sold for $X" | Raw land comps are rare and context-dependent |
| "Zillow estimates this parcel at $X" | Zillow land estimates are unreliable |
| "The seller says developers are interested" | Unverified — seller has incentive to say this |
| "ARV on the finished home would be $X" | ARV is for SFR flips — land requires LDP math |
| No builder activity but good price | Price is irrelevant if there's no buyer for the lots |

---

## Vault Integration

After running Land Comp Logic:
- Note which signals were confirmed in the deal file under `## Valuation`
- Record new construction price used and its source
- If expansion direction was a deciding factor, write an observation in `observations/`
- Link to LDP underwriting result when creating `land/LAND-XXXX.md`
