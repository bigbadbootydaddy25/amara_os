# AMARA Cash Buyer Ingestion

Pulls real grantor/grantee deed records from 6 public county recorder portals, identifies cash transactions (no co-filed Deed of Trust), groups repeat buyers, and exports an AMARA-format buyer registry.

---

## Quick Start

```bash
cd cash-buyer-ingestion
npm install
npx playwright install chromium   # one-time browser download (~140 MB)
node main.js
```

Output files are written to `cash-buyer-ingestion/output/`:
- `cash_buyers_raw.json` — all repeat buyers with full transaction arrays
- `cash_buyers_registry.json` — AMARA registry format
- `scrape_log.json` — per-county record counts, errors, timestamps

### Optional Postgres write

```bash
PG_CONNECTION_STRING=postgres://user:pass@host:5432/dbname node main.js
```

Tables `cash_buyers` and `cash_buyer_transactions` are created automatically.

---

## Portal Reference

| County | State | Portal Type | URL |
|---|---|---|---|
| Dallas | TX | PublicSearch React SPA (REST API + Playwright fallback) | `dallas.tx.publicsearch.us` |
| Harris | TX | ASP.NET WebForms (Playwright) | `cclerk.hctx.net` |
| Bexar | TX | PublicSearch React SPA (REST API + Playwright fallback) | `bexar.tx.publicsearch.us` |
| Clark | NV | ESales REST API (Playwright fallback) | `recorder.clarkcountynv.gov/ESales/` |
| Maricopa | AZ | Web form (Playwright) | `recorder.maricopa.gov/recdocdata/` |
| Polk | FL | Web UI (Playwright) | `apps.polkcountyclerk.net/OfficialRecords/` |

---

## Cash Signal Logic

Each county uses a variation of the same principle:

| County | Cash detection method |
|---|---|
| Dallas, Bexar | No Deed of Trust filed same APN + same recorded date |
| Harris | "CASH" literal in consideration field OR no co-filed DOT |
| Clark (NV) | No DOT filed on same parcel within ±30 days of deed |
| Maricopa | No concurrent DOT filing on same APN + date |
| Polk (FL) | Consideration > 0 AND no mortgage/DOT on same parcel within 30 days |

---

## Known Portal Quirks

### Dallas & Bexar (PublicSearch)
- Tyler Technologies SPA — scraper probes the `/api/instruments/search` endpoint first before launching a headless browser. If the API returns a 404 the scraper falls back to UI automation.
- Document type multi-select uses custom React components, not native `<select>`. The scraper handles both.
- Session cookies may be required for deeper pagination; the browser context handles this automatically.

### Harris County
- Old ASP.NET WebForms app with `__VIEWSTATE` postback. Playwright handles the full page lifecycle.
- Results are in a GridView table. Column ordering is positional — if the portal is redesigned, update column index constants in `harris.js`.
- No APN in search results; DOT cross-check uses document number as a fallback key.

### Clark County (Nevada)
- The ESales API (`/ESales/SearchResults`) uses query parameters; the exact parameter names were derived from browser network traces. If the API changes, inspect Network tab on `recorder.clarkcountynv.gov/ESales/` and update the params in `clark.js → tryESalesApi()`.
- DOT cross-check window is ±30 days (configurable in `crossCheckDots()`).
- Playwright fallback targets the EagleView search portal.

### Maricopa County
- Searches one document type at a time (WARRANTY DEED, SPECIAL WARRANTY DEED, TRUSTEE DEED) because the form doesn't support multi-select.
- A separate DOT search pass is performed to build the cross-check set.
- Pagination uses standard `<a>Next</a>` links; if the portal switches to JS-rendered pagination, add a `waitForLoadState('networkidle')` after click.

### Polk County
- A terms-of-service accept screen may appear on first load; `acceptTermsIfPresent()` handles it.
- Results table column order: Date | Instrument# | DocType | Book/Page | Grantor | Grantee | Consideration | Parcel | Address.
- Both MORTGAGE and DEED OF TRUST are pulled as DOT signals.

---

## Rate Limiting

All scrapers enforce:
- **2–4 second random delay** between every page/API request
- **Maximum 1 concurrent request per county portal** (scrapers run parallel across counties, not within a county)
- **Maximum 2 retries** on any single failed request
- **429 / CAPTCHA detection** — scraper logs the error, returns empty array for that county, and the run continues with other counties
- **robots.txt check** on startup — if the scraper path is disallowed the county is skipped

User-Agent: `AMARA-OS Research Bot / Public Records Access`

---

## Entity Scoring

After grouping by normalized grantee name (suffixes stripped), each entity with **2+ purchases** is scored:

| Signal | Criteria |
|---|---|
| HIGH | `cash_purchases > 3` AND buys in multiple ZIPs |
| MEDIUM | `cash_purchases >= 2` (single or multi-ZIP) |
| LOW | `cash_purchases < 2` or single ZIP only |

Entity type classification:

| Type | Trigger keywords |
|---|---|
| `builder` | HOMES, CONSTRUCTION, BUILDERS, DEVELOPMENT, BUILD, CUSTOM |
| `landlord` | RENTALS, RENTAL, PROPERTIES, HOLDINGS, INVESTMENTS, ASSET, PORTFOLIO |
| `flipper` | (default) |

---

## Adding a New County

1. Create `scrapers/<county>.js` using `utils.js` helpers.
2. Export a single `async function scrape<County>()` that returns `{ county, transactions, errors }`.
3. Each transaction must match the `makeTransaction()` shape from `utils.js`.
4. Add the scraper to the `SCRAPERS` array in `main.js`.
5. Update this README.

Minimum required fields per transaction: `source_county`, `grantee`, `document_date`, `document_number`, `zip`, `cash_flag`.

---

## Piping Output into AMARA Airtable

The registry format (`cash_buyers_registry.json`) maps directly to the AMARA Airtable base `app0jn857ZwVzQs8i`. Use the Airtable REST API to upsert records:

```js
// Example: upsert a single buyer into AMARA Airtable
const AIRTABLE_BASE = 'app0jn857ZwVzQs8i';
const AIRTABLE_TABLE = 'Cash Buyers';  // adjust to your table name
const AIRTABLE_TOKEN = process.env.AIRTABLE_TOKEN;

const registry = JSON.parse(fs.readFileSync('./output/cash_buyers_registry.json'));

for (const buyer of registry.buyers) {
  await fetch(`https://api.airtable.com/v0/${AIRTABLE_BASE}/${encodeURIComponent(AIRTABLE_TABLE)}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${AIRTABLE_TOKEN}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      fields: {
        Name: buyer.name,
        Type: buyer.type,
        'Purchase Count': buyer.purchase_count,
        'Cash Count': buyer.cash_count,
        ZIPs: buyer.zips.join(', '),
        Markets: buyer.markets.join(', '),
        'Min Price': buyer.min_price,
        'Max Price': buyer.max_price,
        'Last Purchase': buyer.last_purchase,
        'Signal Strength': buyer.signal_strength,
        Strategy: buyer.strategy,
      },
    }),
  });
}
```

Set `AIRTABLE_TOKEN` in your environment. Use Airtable's PATCH endpoint with a unique field (e.g., Name) to upsert instead of insert duplicates.

---

## File Structure

```
cash-buyer-ingestion/
├── main.js                     # Orchestrator
├── package.json
├── scrapers/
│   ├── utils.js                # Shared: delay, robots.txt, browser, helpers
│   ├── dallas.js               # Dallas County TX
│   ├── harris.js               # Harris County TX
│   ├── bexar.js                # Bexar County TX (San Antonio)
│   ├── clark.js                # Clark County NV (Las Vegas)
│   ├── maricopa.js             # Maricopa County AZ (Phoenix)
│   └── polk.js                 # Polk County FL (Davenport)
├── processor/
│   └── grouper.js              # Entity grouping, scoring, classification
└── output/
    ├── exporter.js             # JSON + Postgres writer
    ├── cash_buyers_raw.json    # (generated)
    ├── cash_buyers_registry.json  # (generated)
    └── scrape_log.json         # (generated)
```
