# Playbook: AMARA Auto Matcher

## Purpose
Automatically process incoming property leads from any source, run the correct math, match to the best buyer, and queue only profitable deals for offers.

**Core question answered for every lead:**
> Does a real buyer exist? Does the property fit the buy box? What is the real buyer price? What is the MAO? Does it clear the profit lock? Queue for offer — or reject and move on?

---

## Module
`system/auto_matcher.py`

## CLI
```bash
python amara.py match csv leads.csv
python amara.py match manual --address "123 Main St" --zip 77009 --price 145000 --sqft 1200 --dom 45
python amara.py match queue          # view pending offer queue
python amara.py match rejections     # view recent rejections
```

---

## 10-Stage Pipeline

### Stage 1 — Lead Intake
Normalize incoming leads to a standard `PropertyLead`.

**Sources:** Zillow · XLeads · PropStream · Propelio · CSV · Manual entry

**Fields captured:**
- Address, city, state, ZIP, county, parcel ID
- Property type, beds, baths, sqft, lot size, year built
- List price, DOM, price drops
- Keywords extracted from description
- Photos flag, bad photos flag

**Module:** `system/lead_intake.py` → `ingest_from_csv()` or `ingest_manual()`

---

### Stage 2 — Property Classification
Determine processing path before any math runs.

| Classification | Path |
|---------------|------|
| `sfr_wholesale` | SFR comp read + MAO |
| `rental_hedge` | Buy-and-hold buyer match |
| `infill_lot` | Land comp logic + LDP |
| `land_subdivision` | Land comp logic + LDP |
| `dead_paper` | Dead paper scoring + LDP |
| `reject` | Stop — log reason |

**Reject signals:** condo, townhouse, 55+, leasehold, no list price, commercial, mobile

**Module:** `system/lead_intake.py` → `classify_property()`

---

### Stage 3 — Buyer Lookup
Search buyer vault by ZIP, asset type, price band, bed count.

**Buyer-first rule enforced here.** If no buyer matches → pipeline stops.

**Match criteria:**
- ZIP code match (exact)
- Asset type match
- Price within buyer's ceiling (±15% tolerance)
- Bed count ≥ buyer minimum

**Returns:** primary buyer, up to 3 secondary buyers, match score (0–1)

**Module:** `system/auto_matcher.py` → `_lookup_buyers()`
**Vault:** reads `buyers/*.md`

---

### Stage 4 — Comp Reading (SFR)
Determine real buyer price from investor-relevant comps.

**See:** `playbooks/comps/sfr_comp_reading.md`

In auto mode: uses buyer's max price and 85% of list price as conservative estimate.
**Before sending any offer:** replace estimate with live comp read from Zillow/Redfin/PropStream.

---

### Stage 5 — SFR Underwriting
Run MAO formula.

```
MAO = Buyer Price − Repairs − Assignment Fee
```

**Enforced:** Assignment fee ≥ $10,000
**Target:** Assignment fee ≥ $15,000

**See:** `playbooks/underwriting/sfr_fast_math.md`
**Module:** `system/comp_intelligence.py` → `underwrite_sfr()`

If `no_go` → reject at this stage.

---

### Stage 6 — Land / Dead Paper Underwriting
Run LDP formula.

```
Spread = Max Land Value − Asking Price
Max Land Value = Gross Lot Value − Dev Cost − Builder Profit
```

**Enforced:** Spread ≥ $100,000
**Preferred:** $250,000+
**Priority:** $1,000,000+

**See:** `playbooks/underwriting/land_ldp.md`
**See:** `playbooks/comps/land_comp_logic.md`
**Module:** `system/comp_intelligence.py` → `underwrite_land()`

---

### Stage 7 — Distress + Motivation Scoring
Score how motivated the seller is likely to be.

**SFR signals (scored 0–1):**
- DOM (30% weight)
- Price drops (25%)
- Distress keywords (25%)
- Bad photos (20%)
- Boolean bonuses: vacant, inherited, probate, estate, financial distress

**Land signals (scored 0–1):**
- Dead paper (platted/recorded subdivision)
- Ghost streets
- Plat/phase gap
- Builder adjacency
- Ownership weakness (absentee, delinquent taxes, heir property)

**Module:** `system/distress_scorer.py`

---

### Stage 8 — Final Match Score
Weighted composite score.

**SFR:**
```
final_score =
  0.30 × buyer_match_score
  0.25 × profit_score
  0.20 × distress_score
  0.15 × comp_confidence
  0.10 × speed_to_close_score
```

**Land:**
```
final_score =
  0.30 × builder_match_score
  0.25 × spread_score
  0.20 × dead_paper_score
  0.15 × location_score
  0.10 × ownership_score
```

**Grades:** A ≥ 0.80 · B ≥ 0.65 · C ≥ 0.50 · F < 0.50

**Module:** `system/match_scorer.py`

---

### Stage 9 — Approval Gate
Hard rules — all must pass to queue the deal.

**SFR must pass all:**
- [ ] Buyer exists and confirmed
- [ ] `buyer_match_score ≥ 0.40`
- [ ] `assignment_fee ≥ $10,000`
- [ ] Underwriting decision is `go` or `negotiate`

**Land must pass all:**
- [ ] Builder or land buyer exists
- [ ] `spread ≥ $100,000`
- [ ] Underwriting decision is `go` or `conservative`

**Module:** `system/match_scorer.py` → `compute_sfr_final_score()` / `compute_land_final_score()`

---

### Stage 10 — Offer Queue / Rejection Log

**If approved:**
- Creates `OfferRecord` with buyer, MAO/max offer, target fee, notes
- Auto-creates deal stub in `deals/` or `land/` vault
- Routes to offer sender

**If rejected:**
- Logs `RejectionRecord` with stage and reason
- Does NOT create deal file

**Module:** `system/offer_queue.py`

---

## Score Table

| Score | Grade | Action |
|-------|-------|--------|
| ≥ 0.80 | A | Queue immediately |
| 0.65–0.79 | B | Queue — verify comps before sending |
| 0.50–0.64 | C | Queue with caution — confirm buyer first |
| < 0.50 | F | Reject |

---

## What Auto Matcher Does NOT Do
- It does not send offers — it queues them for review
- It does not pull live comps — comp confidence defaults to 0.55 (conservative) until verified
- It does not skip buyer-first logic under any circumstances
- It does not approve deals with fee < $10k or land spread < $100k
