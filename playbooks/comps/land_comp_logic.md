# Land Comp Logic

## Rule
Raw land comps are unreliable. Value land by what builders are paying and selling — not by what raw land last traded for.

---

## The 4 Signals

Check all four. Score: 3/4 = pursue. 2/4 = conservative LDP required. 1/4 or less = stop.

### Signal 1 — Nearby Builders
- Active homebuilder within 1–3 miles?
- National: D.R. Horton, Lennar, KB Home, Pulte, LGI, Taylor Morrison
- Regional / local operators count too
- Find via: Google Maps ("new homes near [city]"), builder websites, county permits
- **Confirms:** Lot demand exists. Builders have already validated the market.

### Signal 2 — Active Subdivisions
- Open phases with active construction?
- Roads being cut, framing, utility work visible?
- Find via: Google Earth satellite, county GIS, physical drive
- **Confirms:** Lot absorption is happening right now in this sub-market.
- **Watch:** Stalled subdivision (graded but overgrown) = demand failure. Investigate before proceeding.

### Signal 3 — New Construction Prices
- What are builders selling finished homes for in this ZIP?
- This is your `median_home_price` input for the LDP formula
- Find via: Builder websites, Zillow new construction filter, MLS
- **If builder prices at premium to existing homes** → strong land market, use 0.23–0.25 lot multiplier
- **If builder prices at parity or discount** → compressed margins, use 0.20–0.22 lot multiplier

### Signal 4 — Expansion Direction
- Is the metro growing toward this parcel?
- New roads, interchanges, water/sewer extensions, employer expansions?
- Find via: City/county GIS, news on infrastructure projects, Google Maps satellite time comparison
- **In the path of growth** → forward premium
- **Behind the growth** → discount or avoid

---

## Decision Rule

| Signals Confirmed | Action |
|------------------|--------|
| 3–4 of 4 | Run LDP (`playbooks/underwriting/land_ldp.md`). Pursue if spread ≥ $100k. |
| 2 of 4 | Run LDP conservatively (low density, 0.20 multiplier). Require spread ≥ $250k. |
| 0–1 of 4 | Do not pursue. Insufficient demand signal. |

---

## What to Use as Median Home Price

Use new construction sale prices in the target ZIP — not existing home prices.
Builders set the ceiling. Existing homes are often below the builder's exit price.

If no new construction is nearby: use existing home median but reduce lot multiplier to 0.18–0.20.

---

## Instant Disqualifiers

- No builder activity within 5 miles
- Flood zone covering >30% of parcel
- No road access and no easement path
- Metro contracting or flat (population decline)
- Seller's price is based on retail residential comps (signal they don't understand land math)
