# Lot Assemblage Opportunities

**Generated:** 2026-05-10 04:42 UTC
**Source:** `data/deal-leads/raw/`
**Total lots ingested:** 15
**Total clusters:** 6
**Builder corridors detected:** 1

---

## Builder Corridors

1 HIGH confidence · 0 MEDIUM confidence · 0 LOW confidence

### Jeff St — 🔥 HIGH CONFIDENCE

| Field | Value |
|---|---|
| Corridor ID | `CORR-JEFF-ST-000` |
| District | Bishop Arts |
| Total Lots | 6 |
| Total Acres | 0.91 |
| Price Range | $39,000 – $52,000 |
| Assemblage Potential | **HIGH** |
| Confidence Score | 100/100 |
| Dominant Broker | John Smith |
| Broker Dispo Confidence | high |
| Strategies | `assemblage_candidate`, `builder_assignment`, `corner_premium`, `infill_build`, `land_flip` |
| Signals | `adjacent_lots`, `bishop_arts`, `cleared_lot`, `corner_lot`, `fenced`, `probate`, `utilities_available` |
| Evidence Files | `infill_lots_dallas.csv` |

**Clusters:** `CLU-JEFF-ST-000`


---

## High-Assemblage Clusters

| Cluster | Street | Lots | Acres | Price Range | Strategies |
|---|---|---|---|---|---|
| `CLU-JEFF-ST-000` | Jeff St | 6 | 0.91 ac | $39,000–$52,000 | assemblage_candidate, builder_assignment, corner_premium |

---

## Broker Frequency & Dispo Confidence

| Broker | Listings | Dispo Confidence | Phone | Email |
|---|---|---|---|---|
| John Smith | 4 | high | `(214) 555-0101` | `jsmith@dallasbrokerage.com` |
| Carlos Reyes | 4 | high | `(214) 555-0303` | `creyes@oakcliffrealty.com` |
| Maria Torres | 3 | medium | `(214) 555-0202` | `mtorres@txrealty.com` |
| Sarah Kim | 2 | medium | `(214) 555-0404` | `skim@dallaslandco.com` |
| David Park | 2 | medium | `(214) 555-0505` | `dpark@southdallasrealty.com` |

---

## Strategy Signals Applied

| Strategy | Boost | Trigger Signals |
|---|---|---|
| `infill_build` | +15 | cleared_lot, utilities_available |
| `builder_assignment` | +20 | bishop_arts, trinity_groves, adjacent_lots |
| `land_flip` | +10 | probate |
| `corner_premium` | +5 | corner_lot |
| `assemblage_candidate` | +8 | adjacent_lots |

---

## Downstream Feeds

| Agent | Records Queued | Feed File |
|---|---|---|
| deal-scoring-engine | 15 | `data/deal-leads/INFILL_CLUSTERS.json` |
| ownership-graph | 15 | `data/deal-leads/INFILL_CLUSTERS.json` |
| portfolio-distress-analysis | 3 | distress-flagged clusters |

---

## Evidence Paths

| Path | Purpose |
|---|---|
| `data/deal-leads/raw/` | Source CSVs |
| `data/deal-leads/INFILL_CLUSTERS.json` | Geo-clustered lots |
| `data/deal-leads/BUILDER_CORRIDORS.json` | Detected corridors |
| `data/deal-scoring/HOT_BUYERS.json` | Buyer cross-reference |
| `data/deal-scoring/ACTIVE_BUYERS.json` | Buyer cross-reference |
| `data/deal-scoring/BUILDER_MATCHES.json` | Builder cross-reference |
