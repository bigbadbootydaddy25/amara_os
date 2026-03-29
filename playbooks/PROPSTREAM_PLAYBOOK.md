# Playbook: PropStream Operator

## Purpose
Use PropStream to identify cash buyers, distressed properties, and target ZIP corridors.
Export structured data and log findings into the vault.

---

## Core Rules

- Never skip the buyer-first check. PropStream is a sourcing tool, not a deal-first tool.
- All exports go to `buyers/`, `deals/`, or `zip-corridors/` — never left as raw files.
- Every search session that produces actionable data must generate at least one vault update.
- Do not create deal files from PropStream data until a buyer match is confirmed.

---

## Module 1 — Login and Navigation

### 1.1 Login
1. Go to app.propstream.com
2. Login with credentials (stored securely outside vault)
3. Confirm subscription tier supports the features needed:
   - Cash buyer search requires access to deed/transfer records
   - Distress filters (foreclosure, pre-foreclosure, tax delinquent) require full data tier
   - List exports require an active export credit balance

### 1.2 Navigation Map
```
Dashboard
├── Search Properties          — individual property lookup
├── List Builder               — bulk filtering by criteria
│   ├── Property Filters       — type, bed/bath, sqft, year, value
│   ├── Owner Filters          — absentee, out-of-state, LLC-owned
│   ├── Distress Filters       — foreclosure, pre-foreclosure, tax liens, bankruptcy
│   ├── Equity Filters         — high equity, free & clear
│   └── Transaction Filters    — cash sales, recent sales, MLS status
├── Cash Buyer Search          — identify repeat cash buyers by ZIP
├── Saved Searches             — stored filter sets
└── My Lists                   — exported and saved property lists
```

---

## Module 2 — Cash Buyer Identification

### 2.1 Find Repeat Cash Buyers by ZIP

**Use: List Builder → Transaction Filters**

Filter settings:
- Property Type: SFR (Single Family Residential)
- Sale Type: Cash
- Sale Date: Last 24 months
- ZIP Code(s): Target corridor ZIPs
- Transactions: 2+ (repeat buyers only — single transactions are often owner-occupants)

Sort by: Number of transactions (descending)

**What to look for:**
- LLC or company name buyer = investor
- Same buyer entity appearing 3+ times = active operator
- Buyer address out-of-state or different ZIP = absentee investor / portfolio builder

### 2.2 Qualify the Buyer
Before creating a buyer file, verify:
- [ ] Buyer has 2+ cash transactions in last 24 months in target ZIP
- [ ] Entity name suggests investor (LLC, Holdings, Capital, Investments, Properties, Group)
- [ ] Purchase price range consistent with wholesale buy box
- [ ] Not a builder or developer (those are land buyers, route to `land/`)

### 2.3 Extract Buyer Data
Pull from PropStream record:
- Buyer name / entity
- Mailing address (for contact)
- Properties purchased (addresses, prices, dates)
- Average purchase price
- Purchase ZIPs

**Log to vault:** Create `buyers/BUY-XXXX_Name.md` using `buyers/TEMPLATE.md`

---

## Module 3 — Distressed Property Search

### 3.1 Pre-Foreclosure / NOD Search

**Use: List Builder → Distress Filters → Pre-Foreclosure / Notice of Default**

Filter settings:
- Property Type: SFR
- ZIP Code(s): Active buyer corridor ZIPs only
- NOD Filing Date: Last 90 days (freshest leads)
- Equity: 20%+ (seller has something to protect — more likely to sell)

**Do not work:** Properties with negative equity (seller underwater — no spread possible)

### 3.2 Tax Delinquent Search

**Use: List Builder → Distress Filters → Tax Delinquent**

Filter settings:
- Property Type: SFR
- ZIP Code(s): Target ZIPs
- Tax Delinquency: 1+ years
- Estimated Value: Within buyer's buy box range

Note: Tax delinquent sellers often have time — don't assume urgency. Lead with problem-solving language.

### 3.3 Absentee Owner + High Equity Search

**Use: List Builder → Owner Filters + Equity Filters**

Filter settings:
- Owner: Absentee (mailing address ≠ property address)
- Owner Type: Individual (not LLC — those are investors who may be buyers)
- Equity: 40%+ or Free & Clear
- Last Sale: 5+ years ago (longer hold = more motivated to exit)
- Property Type: SFR

High equity + long hold + absentee = highest motivated seller profile.

### 3.4 Vacant / Zombie Property Search

**Use: List Builder → Property Filters → Occupancy: Vacant**

- Cross-reference with tax delinquency for strongest leads
- Vacant + tax delinquent + absentee = triple distress signal

---

## Module 4 — Saving and Exporting Searches

### 4.1 Save Search Templates
After building a high-performing filter set:
1. Click **Save Search** in List Builder
2. Name format: `[MARKET]-[TYPE]-[DATE]`
   - Example: `HOUSTON-77009-CASH-BUYERS-2026Q1`
   - Example: `PHOENIX-85033-PREFORECLOSURE-2026Q1`
3. Set alert: Weekly refresh on saved searches in active corridors

### 4.2 Export List
1. Select records from filtered results
2. Click **Export** → choose CSV
3. Fields to include: Owner Name, Property Address, Mailing Address, Estimated Value, Equity %, Last Sale Date, Last Sale Price, Distress Flags, Phone (if skip-traced)
4. Save export to local working folder — do not commit raw CSVs to vault

### 4.3 Process Export into Vault
After export:
- Cash buyer exports → screen each record → create `buyers/BUY-XXXX.md` for qualified buyers
- Distressed property exports → screen each record against active buyer buy boxes → create `deals/DEAL-XXXX.md` only for buyer-matched properties
- Market-level aggregate data → update or create `markets/` and `zip-corridors/` files

---

## Module 5 — ZIP Corridor Heat Mapping

### 5.1 Identify Active ZIPs
**Use: Cash Buyer Search → filter by ZIP → sort by transaction volume**

A ZIP is **hot** if:
- 5+ unique cash buyers active in last 12 months
- Average cash transaction volume ≥ 3 deals per buyer
- Median cash sale price is within buyer buy box range

**Log to vault:** Update `zip-corridors/ZIP-XXXX.md` with buyer count, price range, and activity level.

### 5.2 Dead ZIPs to Avoid
Signs of a cold corridor:
- Fewer than 2 cash buyers in last 24 months
- Cash sale prices inconsistent (wide spread = unreliable comps)
- High DOM on retail MLS in the same ZIP

---

## Module 6 — PropStream Data Logging Protocol

Every PropStream session that produces usable data must result in at least one of:

| Output | Vault Location |
|--------|---------------|
| New cash buyer identified | `buyers/BUY-XXXX.md` |
| New distressed property (buyer matched) | `deals/DEAL-XXXX.md` |
| ZIP corridor heat map update | `zip-corridors/ZIP-XXXX.md` |
| Market pricing observation | `observations/OBS-XXXX.md` |

Do not end a PropStream session without logging. Raw exports that never reach the vault are wasted intelligence.

---

## Saved Search Library

| Name | Market | Type | Refresh |
|------|--------|------|---------|
| *(add as searches are saved)* | | | |

---

## Notes
- Skip-tracing is not built into PropStream — use a separate skip-trace tool after export
- PropStream data is 24–72 hours delayed on some markets — confirm critical deal data with county records
- LLC buyer entities require manual research (registered agent search) to find actual contact
