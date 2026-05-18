# AMARA BRAIN — Clark County NV Tax Delinquent OSINT
**Generated:** 2026-05-18  
**Jurisdiction:** Clark County, Nevada  
**Data Sources:** 2021 Trustee Auction Notice + 2024 Annual Delinquency Publication

---

## What's In This Folder

| File | Description | Records |
|------|-------------|---------|
| `parcel_master_ranked.csv` | All parcels ranked by motivation score | 175 |
| `hot_targets.csv` | Strong/Hot targets (score 60+) | 7 |
| `deceased_probate_targets.csv` | Estate, trust, and probate signals | 44 |
| `entity_distress_targets.csv` | LLC/corp/entity owners | 107 |
| `title_red_flags.csv` | ETAL, group sales, owner changes, trusts | 59 |
| `auction_sale_date_calendar.csv` | 2021 auction parcels with sale dates | 75 |
| `manual_review_queue.csv` | Score 40+ parcels needing OSINT verification | 40 |
| `source_log.md` | Full provenance of every data point | — |
| `execution_report.md` | Analysis, top targets, outreach list | — |
| `README.md` | This file | — |

---

## Quick Start

1. **Open `hot_targets.csv`** — your immediate action list (7 STRONG TARGETs from 2021 auction)
2. **Read `execution_report.md`** — full analysis, top 10 targets, outreach recommendations
3. **Work through `manual_review_queue.csv`** — 40 parcels needing Assessor/Recorder/NV SOS lookup
4. **Check `source_log.md`** — source URLs for every public record check

---

## Scoring Legend

| Score | Class | Meaning |
|-------|-------|---------|
| 80–100 | HOT TARGET | Act immediately |
| 60–79 | STRONG TARGET | Priority outreach within 2 weeks |
| 40–59 | WATCHLIST | Needs more data; re-score after verification |
| 0–39 | LOW PRIORITY | Monitor only |

**Note:** Scores will increase significantly once you run manual verification.
Many WATCHLIST parcels will upgrade to HOT TARGET after Assessor + Recorder + NV SOS checks.

---

## Key Findings Summary

- **75 auction parcels** from 2021 Clark County Trustee Sale — all 3+ years delinquent
- **8,660 parcels** in 2024 annual delinquency publication
- **15 APNs** appear in BOTH lists — extreme distress, 5+ years continuous delinquency
- **Top estate target:** BADALI JOSEPHINE ESTATE (APN 139-15-210-256) — search probate NOW
- **Top LLC portfolio distress:** C & C LAS VEGAS LLC — 55 delinquent parcels in 2024
- **Top value auction parcel:** EPSTEIN KENNETH — $294,845 min bid at 9517 Gold Bank Dr
- **Top cross-referenced distress:** LEAVITT LEROY J — delinquent in BOTH 2021 and 2024

---

## Public Sources for Manual Verification

- **Assessor:** https://assessor.clarkcountynv.gov/assrapp/assessment/SitePages/showDetail.aspx
- **Treasurer:** https://treasurer.clarkcountynv.gov/treasurer-home/real-property-tax-inquiry
- **Recorder:** https://recorder.clarkcountynv.gov/forsearch/search
- **Courts/Probate:** https://www.clarkcountycourts.us/Anonymous/default.aspx
- **NV SOS Entity:** https://esos.nv.gov/EntitySearch/OnlineEntitySearch
- **Bid4Assets (auction):** https://www.bid4assets.com/ClarkNV

---

## Data Integrity

All data sourced directly from official Clark County government documents.  
No data invented. Fields marked UNVERIFIED require external lookup.  
See `source_log.md` for full provenance chain.
