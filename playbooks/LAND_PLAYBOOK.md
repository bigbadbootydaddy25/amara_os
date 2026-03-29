# Playbook: Land / Dead Paper

## Deal Type
Raw Land, Infill Lots, Agricultural, Dead Paper (distressed land notes)

---

## Core Rules (Non-Negotiable)

1. **Buyer-first.** No buyer = no deal.
2. **Minimum spread: $100,000** — never go below.
3. **Target: 6–8 figure spreads.**
4. **Spread formula:**
   ```
   Spread = Developer/Retail Value − Acquisition Cost − Assignment Fee
   ```

---

## Step-by-Step Workflow

### Step 1 — Confirm Buyer / Developer Demand
- Search `buyers/` for active land buyers matching:
  - Asset type: Land
  - State / County / Region
  - Acreage and use type
- If no buyer → do not pursue
- If buyer → note their target use case, price per acre, and entitlement requirements

### Step 2 — Parcel Intake
Gather:
- [ ] APN + legal description
- [ ] Acreage
- [ ] Zoning
- [ ] Entitlements (none / partial / approved)
- [ ] Utilities (none / partial / full)
- [ ] Road access
- [ ] Flood zone status
- [ ] Seller asking price
- [ ] Seller motivation and timeline
- [ ] County / municipality

### Step 3 — Establish Retail / Developer Value
**This is the most critical step for land.**
- Pull sales comps from county records (same zone, same acreage range, last 12–24 months)
- Contact 2–3 developers to validate interest and offer range
- Check price per acre in the corridor
- **Do not use residential ARV logic for land**
- Record in `land/[DEAL].md`

### Step 4 — Calculate Spread

```
Developer / Retail Value:       $__________
Acquisition Cost (contract):  - $__________
Assignment Fee (if any):      - $__________
───────────────────────────────────────────
Net Spread:                     $__________
```

**Minimum Spread: $100,000**
**Target: $500,000 – $10,000,000+**

If spread < $100,000 → do not pursue unless there is a clear path to value increase.

### Step 5 — Match Buyer / Developer
- Search `buyers/` for land buyers in the corridor
- Send opportunity with:
  - Parcel description (blind if needed)
  - Acreage + zoning
  - Entitlement status
  - Your asking price
  - Comparable sales

### Step 6 — Send Offer to Seller
- Once buyer / developer confirms interest → offer acquisition price
- Preferred: use option agreement or assignable purchase contract
- Keep option period long enough to find buyer if one isn't confirmed

### Step 7 — Record Outcome
- See `deal-results/TEMPLATE.md`
- Run learning protocol post-close

---

## Land Deal Red Flags

| Issue | Action |
|-------|--------|
| No comps — unproven market | Validate with 2+ developers before proceeding |
| Zoning doesn't match buyer need | Confirm buyer will accept or seek rezoning path |
| Flood zone / environmental issues | Get survey + environmental report before offer |
| Spread < $100,000 | Walk away |
| Seller has unrealistic price expectations | Educate or move on |
| Entitlement uncertainty | Price discount to reflect risk |

---

## Spread Quick Reference

| Retail Value | Acquisition | Spread | Viable? |
|-------------|-------------|--------|---------|
| $500,000 | $350,000 | $150,000 | Yes |
| $1,000,000 | $500,000 | $500,000 | Yes — Target |
| $5,000,000 | $1,000,000 | $4,000,000 | Excellent |
| $200,000 | $150,000 | $50,000 | NO — below minimum |
| $300,000 | $250,000 | $50,000 | NO — below minimum |

---

## Dead Paper (Land Notes)

For distressed notes on land:
- Confirm the underlying collateral value
- Apply spread formula to note discount
- Minimum spread still applies: $100,000
- Key risk: title, IRS liens, HOA super-liens

---

## Vault Links
- Buyers: `buyers/`
- Land Deals: `land/`
- Markets: `markets/`
- ZIP Corridors: `zip-corridors/`
- Observations: `observations/`
