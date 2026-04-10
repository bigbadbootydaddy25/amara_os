# PropStream Data Extraction & Deal-Matching System

## Quick Start

1. **Copy and fill credentials:**
   ```bash
   cp scripts/propstream/.env.propstream.example scripts/propstream/.env.propstream
   # Edit .env.propstream with your PropStream email + password
   ```

2. **Install Playwright browser** (first time only):
   ```bash
   npx playwright install chromium
   ```

3. **Inspect live DOM first** (recommended before full run):
   ```bash
   npm run propstream:inspect
   ```
   Check `scripts/propstream/data/dom-inspection-report.json` and 
   `scripts/propstream/screenshots/` to verify selectors are correct.

4. **Run the full pipeline:**
   ```bash
   npm run propstream
   ```

## Commands

| Command | Description |
|---|---|
| `npm run propstream` | Full run: scrape → process → export |
| `npm run propstream:inspect` | DOM inspection only (no data written) |
| `npm run propstream:scrape` | Scrape only (resumes from checkpoint) |
| `npm run propstream:process` | Process existing raw data, write output files |
| `npm run propstream:airtable` | Push existing output to Airtable |

## Output Files (project root)

| File | Description |
|---|---|
| `sfr_targets_by_zip.csv` | All SFR / distress targets, sorted by ZIP |
| `land_targets_by_zip.csv` | All land targets, sorted by ZIP |
| `sfr_buyers.json` | SFR cash buyer profiles |
| `land_buyers.json` | Land / builder buyer profiles |
| `sfr_match_board.json` | SFR properties matched to buyers |
| `builder_match_board.json` | Land/dead paper matched to builders |
| `dead_paper_targets.json` | Dead paper / expiring entitlements (sorted by urgency) |
| `ghost_subdivision_targets.json` | Recorded plats with zero permits |
| `propstream_run_summary.json` | Run stats and counts |
| `raw_<list_name>.json` | Raw scraped data per list (19 files, in `/data/`) |

## Architecture

```
main.ts                    ← Orchestrator (phases 1-3)
config/
  zips.ts                  ← All target ZIPs, markets, tiers
  lists.ts                 ← Lead list names and track assignments
lib/
  browser.ts               ← Playwright setup with stealth
  auth.ts                  ← PropStream login
  rate-limiter.ts          ← Request throttling
  dom-inspector.ts         ← Live DOM discovery (run before scraping)
  storage.ts               ← File I/O and checkpoint/resume
scrapers/
  list-scraper.ts          ← 19-list scraper with pagination + retry
processors/
  normaliser.ts            ← Raw fields → structured records
  sfr.ts                   ← SFR track filter + deduplication
  land.ts                  ← Land classification + urgency scoring
  buyers.ts                ← SFR and land buyer profile builder
matchers/
  match-board.ts           ← Cross-reference targets against buyers
exporters/
  csv.ts                   ← CSV output
  json.ts                  ← JSON output files
  airtable.ts              ← Airtable push (requires API key)
```

## Urgency Scoring (Land / Dead Paper)

| Score | Condition |
|---|---|
| 100 | Expired entitlement |
| 95 | ≤30 days to expiry |
| 85 | ≤60 days to expiry |
| 75 | ≤90 days to expiry |
| 80 | Ghost subdivision (plat + zero permits) |
| 75 | Dead paper subdivision |

Anything ≥75 is flagged `flagForImmediateAction: true` in the match board.

## Notes

- Scraping resumes automatically from checkpoint if interrupted
- Each list is saved to its own raw JSON file as it completes
- Records with missing critical fields are flagged `incomplete: true` (never silently dropped)
- SFR and land buyer profiles are kept strictly separate
- Airtable push requires AIRTABLE_API_KEY (prompted if not in .env)
