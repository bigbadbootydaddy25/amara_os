# AMARA OS

Buyer-first real estate acquisition intelligence system.

**Core rule: No buyer = no deal.**

---

## Quick Start

```bash
git clone https://github.com/bigbadbootydaddy25/amara_os
cd amara_os

# Run CLI
python amara.py

# Start REST API
python amara.py orchestrate api
# or
uvicorn api.main:app --reload --port 8000

# Run tests
pip install pytest
python -m pytest tests/ -q
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AMARA_VAULT_ROOT` | `./` | Absolute path to vault root directory |
| `AMARA_DEBUG` | `false` | Enable debug logging |
| `DATABASE_URL` | `postgresql://localhost/amara` | Postgres connection string for schema |
| `AMARA_SENDER_NAME` | `AMARA Acquisitions` | Offer letter sender name |
| `AMARA_MIN_DISTRESS_SCORE` | `0.30` | Minimum distress score to pass Zillow hunt |

---

## System Architecture

```
amara.py                  CLI entry point
api/main.py               FastAPI REST API
system/                   Core intelligence modules
  config.py               Constants: minimums, vault paths, statuses
  mao_calculator.py       MAO formula, LDP formula
  deal_analyzer.py        SFR + land deal analysis
  buyer_matcher.py        Buy box matching
  vault.py                Markdown vault read/write
  comp_intelligence.py    Fast underwriting (<60s rule)
  lead_intake.py          CSV + manual lead ingestion
  distress_scorer.py      SFR + land distress scoring
  match_scorer.py         Weighted composite scoring (Stage 8/9)
  offer_queue.py          Offer queue management
  auto_matcher.py         10-stage pipeline orchestrator
  buyer_discovery.py      Buyer scoring + buy box inference
  zillow_hunter.py        Distress hunt from Zillow exports
  offer_sender.py         Offer message generation + follow-up scheduler
  learning_engine.py      Feedback loop: intake, observation, buyer/market update
  entitlement_engine.py   Land entitlement scoring
  approval_tracker.py     Entitlement pipeline stage tracking
  orchestrator.py         Scheduled + event-driven workflow runner
  propstream_operator.py  PropStream CSV import
  video_to_playbook.py    Video transcript to playbook
  learning_protocol.py    Post-close learning (legacy)
  zip_corridor.py         ZIP corridor management
  schema.sql              Full database schema (PostgreSQL)
tests/                    Unit tests (pytest)
playbooks/                System playbooks
buyers/                   Vault: buyer profiles
deals/                    Vault: SFR deal files
land/                     Vault: land deal files + entitlement records
markets/                  Vault: city/metro snapshots
zip-corridors/            Vault: ZIP demand data
observations/             Vault: market intelligence
deal-results/             Vault: closed deal records
offers/                   Vault: offer letters + follow-up logs
```

---

## CLI Commands

### Pipeline

```bash
# Run Auto Matcher on a CSV
python amara.py match csv leads.csv --source zillow

# Run Auto Matcher on a single lead
python amara.py match manual \
  --address "4901 Crane St" --zip 77008 --price 128000 \
  --sqft 1400 --beds 3 --year-built 1985 --dom 45

# View pending offer queue
python amara.py match queue

# View rejection log
python amara.py match rejections
```

### MAO Calculator

```bash
# SFR MAO
python amara.py mao sfr --buyer-price 200000 --repairs 30000
python amara.py mao sfr --buyer-price 200000 --repairs 30000 --seller-asking 145000

# Land spread
python amara.py mao land --retail-value 1000000 --acquisition 400000
```

### Underwriting

```bash
# SFR fast underwrite
python amara.py underwrite sfr \
  --deal-id DEAL-001 --address "4901 Crane" --zip 77008 \
  --buyer-price 175000 --seller-asking 140000 --repairs 25000

# Land underwrite with signals
python amara.py underwrite land \
  --deal-id LAND-001 --acres 15 --median-home-price 380000 \
  --asking-price 600000 --builders --subdivisions

# LDP formula direct
python amara.py ldp --acres 20 --median-home-price 400000 --asking-price 800000
```

### Zillow Distress Hunting

```bash
# Score a Zillow CSV export for distress signals
python amara.py hunt score --file zillow_export.csv

# Show search criteria for active buyer ZIPs
python amara.py hunt criteria

# Show criteria for specific ZIPs
python amara.py hunt criteria --zips 77008,77009,77018 --max-price 250000
```

### Entitlement Analysis (Land)

```bash
# Quick entitlement screen
python amara.py entitle \
  --deal-id LAND-001 --address "100 Dev Blvd" --zip 78701 \
  --zoning R2 --water --sewer --road --plat preliminary \
  --permits pre_app --write

# Dead paper deal
python amara.py entitle \
  --deal-id LAND-002 --address "Ghost St" --zip 77014 \
  --dead-paper --plat recorded --write
```

### Approval Tracker (Land Pipeline)

```bash
# Create approval record
python amara.py approve create \
  --deal-id LAND-001 --address "100 Dev Blvd" --zip 78701 \
  --county Travis --stage pre_app

# Advance to next stage
python amara.py approve advance --id APR-XXXXXX

# Record a revision
python amara.py approve revision --id APR-XXXXXX

# List all approval records
python amara.py approve list
```

### Close a Deal (Learning Protocol)

```bash
python amara.py close \
  --deal-id DEAL-0001 --address "4812 Crane St" --zip 77008 \
  --buyer-id BUY-0001 --buyer-name "Marcus Webb" \
  --proj-buyer-price 175000 --proj-repairs 30000 \
  --proj-mao 130000 --proj-fee 15000 \
  --actual-contract 128000 --actual-buyer-price 178000 \
  --actual-repairs 27000 --actual-fee 23000
```

### Buyer Discovery

```bash
python amara.py discover rank
```

### Orchestrator

```bash
# Run a scheduled workflow manually
python amara.py orchestrate run --workflow nightly_buyer_refresh
python amara.py orchestrate run --workflow deal_hunt
python amara.py orchestrate run --workflow morning_offer_queue
python amara.py orchestrate run --workflow followup_sweep
python amara.py orchestrate run --workflow learning_sync

# Dispatch an event
python amara.py orchestrate event \
  --event-name deal_closed \
  --payload '{"deal_id":"DEAL-001","address":"4812 Crane","zip_code":"77008","asset_type":"SFR","buyer_id":"BUY-001","buyer_name":"Marcus Webb","projected_buyer_price":175000,"projected_repairs":30000,"projected_mao":130000,"projected_fee":15000,"actual_contract_price":128000,"actual_buyer_price":178000,"actual_repairs":27000,"actual_fee":23000}'

# View orchestrator status
python amara.py orchestrate status

# Start REST API server
python amara.py orchestrate api
```

### PropStream

```bash
# Import cash buyers from PropStream export
python amara.py propstream import-buyers buyers_export.csv --market "Houston North"

# Import distressed properties (buyer-matched)
python amara.py propstream import-distressed props_export.csv \
  --buyer-zips 77008,77009,77018 \
  --buyer-id BUY-0001 --buyer-name "Marcus Webb"
```

### Learn (Video-to-Playbook)

```bash
python amara.py learn transcript.txt --title "Deal Structuring Masterclass"
```

### Vault

```bash
python amara.py vault list buyers
python amara.py vault list deals
python amara.py vault search buyers "Dallas"
python amara.py vault search observations "Houston"
```

---

## REST API

Once running (`python amara.py orchestrate api` or `uvicorn api.main:app`):

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | System health + vault counts |
| POST | `/leads/manual` | Run pipeline on single lead |
| POST | `/leads/csv` | Run pipeline on CSV upload |
| GET | `/queue` | View offer queue |
| GET | `/queue/{offer_id}` | Get specific offer |
| GET | `/rejections` | View rejection log |
| POST | `/deals/close` | Record closed deal + learning |
| POST | `/events` | Dispatch workflow event |
| GET | `/workflows` | List workflows |
| POST | `/workflows/run` | Run a scheduled workflow |
| GET | `/workflows/history` | Job history |
| GET | `/buyers` | List vault buyers |
| POST | `/entitlement` | Run entitlement analysis |
| POST | `/approval` | Create approval record |
| GET | `/approval/{id}` | Get approval status |
| PATCH | `/approval/{id}/advance` | Advance stage |
| PATCH | `/approval/{id}/revision` | Log revision |
| GET | `/approval` | List all approvals |

Interactive docs: `http://localhost:8000/docs`

---

## Database Schema

Run `system/schema.sql` against PostgreSQL to initialize all tables.

**Tables:**
- `properties`, `property_classifications`, `property_matches` — pipeline stages 1-3
- `property_underwriting`, `comp_reads` — underwriting stages 4-6
- `distress_scores`, `match_scores` — scoring stages 7-8
- `offer_queue`, `rejection_log` — pipeline output
- `buyers`, `buyer_transactions`, `buyer_buyboxes` — buyer discovery
- `zip_liquidity` — ZIP demand data
- `learning_events`, `entity_updates` — learning feedback loop
- `workflows`, `workflow_jobs`, `workflow_events` — orchestration
- `land_entitlements`, `approval_status` — land deal tracking
- `offer_followups` — follow-up scheduler

---

## MAO Formula

```
Buyer Price (what investor pays):   $
Repairs (conservative estimate):  - $
Assignment Fee (target $15,000):  - $15,000
─────────────────────────────────────────
MAO:                                $
```

**Minimums (never override):**
- SFR assignment fee: `$10,000` hard floor, `$15,000` target
- Land spread: `$100,000` hard floor, `$500,000` target

**Do NOT use the 70% ARV rule.**

---

## LDP Formula (Land)

```
Gross Acres x Net Factor (0.75)        = Net Developable Acres
Net Acres x Density (3.5 lots/acre)    = Estimated Lots
Lots x Lot Value (23% of median home)  = Gross Lot Value
Gross Value - Dev Cost ($60k/lot)      = Pre-Profit Value
Pre-Profit Value x (1 - 0.15 margin)  = Max Land Value
Max Land Value - Asking Price          = Spread
```

---

## Vault Structure

```
buyers/           Who buys. What they pay. Where they buy.
deals/            Active and closed SFR deals.
land/             Land, dead paper, entitlement, approval records.
markets/          City and metro snapshots.
zip-corridors/    ZIP-level activity and buyer demand.
playbooks/        Step-by-step workflows.
observations/     Market intelligence.
deal-results/     Closed deal records and post-mortems.
offers/           Offer letters and follow-up logs.
system/           Python modules.
```

---

## Tests

```bash
python -m pytest tests/ -q
# 131 tests:
#   test_mao_calculator.py    - MAO, LDP, land spread, fee calculations
#   test_auto_matcher.py      - 10-stage pipeline, buyer lookup, repair estimates
#   test_match_scorer.py      - Scoring weights, approval gate, grade logic
#   test_buyer_discovery.py   - Activity scoring, buy box inference, ZIP liquidity
#   test_entitlement_engine.py - Zoning, infra, plat, permit scoring
#   test_learning_engine.py   - Gap analysis, verdicts, recommendations
#   test_approval_tracker.py  - Stage tracking, backlog scoring, next steps
```
