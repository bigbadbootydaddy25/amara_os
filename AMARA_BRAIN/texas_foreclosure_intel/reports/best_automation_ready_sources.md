# Best Automation-Ready Foreclosure Sources

**Report:** AMARA-AI Texas Foreclosure Intel  
**Focus:** Technical Automation Feasibility, Implementation Approach, Developer Effort Estimates  
**Markets:** Harris County (Houston), Dallas County (Dallas), Tarrant County (Fort Worth / Arlington)  
**Date:** 2026-05-16  

---

## Executive Summary

Automation transforms the AMARA-AI foreclosure intelligence module from a manual research tool into a continuously operating lead pipeline. This report ranks the best Texas foreclosure sources by **automation readiness** — the combination of data accessibility, structural consistency, absence of blockers (CAPTCHA, login walls, JavaScript rendering), and return on automation investment.

**Automation Score Scale (1–10):**
- 9–10: Fully automatable with API or clean HTTP — minimal maintenance required
- 7–8: Good automation potential — PDF parsing or light scraping required
- 5–6: Moderate — some manual steps or Playwright rendering required
- 3–4: Low automation value — mostly manual
- 1–2: Physical or inaccessible — manual only

---

## Rank 1 — PropertyRadar (Score: 9/10)

**Website:** https://www.propertyradar.com  
**Automation Method:** API  
**Blocker:** SUBSCRIPTION_WALL  
**Recommended Priority:** HIGH  
**Counties:** Harris, Dallas, Tarrant  

### What to Automate

- Daily fetch of new trustee-sale notices across all three Texas counties
- Ongoing alerts for new filings matching defined criteria (ZIP, equity threshold, property type)
- Nightly bulk export of the upcoming first-Tuesday sale list for lead processing

### How to Automate

PropertyRadar exposes a documented REST API available to enterprise subscribers. The automation architecture is:

1. **Authentication:** OAuth token-based API authentication
2. **Endpoint:** Foreclosure/trustee-sale search endpoint, filtered by TX state + target counties
3. **Parameters:** Filter by `event_type=trustee_sale`, `state=TX`, `county=[target]`, `status=pending`
4. **Response:** JSON array of matching properties with full data fields
5. **Schedule:** Nightly cron job — new records pushed to AMARA-AI lead database
6. **Deduplication:** Hash on property address + sale date to prevent duplicate records

### What Data You Get

| Field | Available |
|---|---|
| Property address | YES |
| Owner name | YES |
| Owner mailing address | YES (pre-enriched) |
| Opening bid | YES |
| Unpaid balance | YES |
| Sale date | YES |
| Trustee firm name | YES |
| AVM / property value | YES |
| Equity estimate | YES |

### Blockers

- **SUBSCRIPTION_WALL** — requires paid subscription with API access tier; standard subscriptions may not include API access

### Estimated Dev Effort

- API integration with authentication and data mapping: **2–3 days**
- Deduplication logic and database schema: **1 day**
- Alert system and monitoring: **1 day**
- **Total:** 4–5 days

---

## Rank 2 — ATTOM Data Solutions (Score: 9/10)

**Website:** https://www.attomdata.com  
**Automation Method:** API  
**Blocker:** SUBSCRIPTION_WALL (enterprise pricing)  
**Recommended Priority:** HIGH  
**Counties:** All Texas counties  

### What to Automate

- Daily foreclosure event feed (new filings, auction events, post-sale status)
- Monthly bulk extract of all pending Texas trustee-sale events for portfolio analysis
- Post-sale data ingestion (buyer entity, sale price, REO vs. third-party buyer)

### How to Automate

ATTOM provides a structured data API with multiple relevant endpoints:

1. **API Authentication:** API key passed in request headers
2. **Foreclosure Events Endpoint:** Returns pending trustee-sale events with full legal and property data
3. **Post-Sale Events Endpoint:** Returns disposition data after each auction date
4. **Property Detail Endpoint:** AVM, characteristics, ownership history
5. **Bulk Delivery:** ATTOM also supports SFTP file delivery for large-volume institutional subscribers

### What Data You Get

| Field | Available |
|---|---|
| Property address | YES |
| Owner name | YES |
| Opening bid | YES |
| Unpaid balance | YES |
| Sale date | YES |
| Trustee firm | YES |
| Lender / servicer | YES |
| AVM | YES |
| Post-sale buyer entity | YES |
| Historical foreclosure data | YES |

### Blockers

- **SUBSCRIPTION_WALL** — enterprise pricing; contact ATTOM sales for institutional rate

### Estimated Dev Effort

- API integration and field mapping: **3–4 days**
- Post-sale event pipeline: **2 days**
- Historical backfill: **1–2 days**
- **Total:** 6–8 days

---

## Rank 3 — BDF Group / Barrett Daffin (Score: 8/10)

**Website:** https://www.bdfgroup.com/foreclosure-posting/  
**Automation Method:** PDF_PARSE + HTTP_GET  
**Blockers:** None  
**Recommended Priority:** HIGH  
**Cost:** Free  

### What to Automate

- Monthly download of Harris, Dallas, and Tarrant County foreclosure notice PDFs
- PDF parsing to extract structured records (address, owner, bid, date, trustee)
- Load into AMARA-AI lead database

### How to Automate

BDF Group uses a straightforward public posting system with no login required:

1. **Discovery:** HTTP GET to the BDF Group foreclosure posting page
2. **Link Extraction:** Parse HTML for county-specific PDF download links (typically updated on or around the 5th of each month)
3. **Download:** HTTP GET request to download each county PDF
4. **Parse:** PDF text extraction using a library (PyPDF2, pdfplumber, or similar)
5. **Field Extraction:** Regex or layout-based extraction of:
   - Property address (street, city, county, ZIP)
   - Owner / borrower name
   - Opening bid amount
   - Sale date
   - Trustee name
   - Deed of trust instrument reference
6. **Load:** Insert into AMARA-AI database with source attribution

### What Data You Get

| Field | Available |
|---|---|
| Property address | YES |
| Owner name | YES |
| Opening bid | YES |
| Sale date | YES |
| Trustee info | YES |
| Lender/servicer | SOMETIMES |

### Blockers

- **None significant** — PDFs are publicly accessible
- **Schema drift risk** — BDF Group may occasionally change PDF layout; parser requires periodic validation
- **PDF quality** — scanned vs. text PDFs may require different parsing approaches

### Estimated Dev Effort

- HTTP scraper for PDF link discovery and download: **1 day**
- PDF parser (field extraction, regex development): **2–3 days**
- Data validation and error handling: **1 day**
- Scheduled automation (cron): **0.5 day**
- **Total:** 4–5.5 days (per county; reuse parser for Harris/Dallas/Tarrant)

---

## Rank 4 — Mackie Wolf Zientz & Mann PC (Score: 8/10)

**Website:** https://www.mwzmlaw.com/foreclosure-postings/  
**Automation Method:** PDF_PARSE + HTTP_GET  
**Blockers:** None  
**Recommended Priority:** HIGH  
**Cost:** Free  

### What to Automate

Same workflow as BDF Group — monthly PDF download and parse for Harris, Dallas, and Tarrant Counties.

### How to Automate

Essentially identical automation architecture to BDF Group:
1. HTTP GET to mwzmlaw.com/foreclosure-postings/
2. Extract county-specific PDF download links
3. Download PDFs
4. Parse with same or similar parser (field layouts may differ slightly from BDF)
5. Load into AMARA-AI database

### What Data You Get

Same fields as BDF Group — property address, owner name, opening bid, sale date, trustee.

### Blockers

- None significant — public access without login
- May require separate PDF parser from BDF Group if layout differs significantly

### Estimated Dev Effort

- Largely reuses BDF Group automation infrastructure
- Incremental effort: **1–2 days** (new HTTP connector + PDF parser validation/adjustment)
- **Total with BDF Group infrastructure:** 1–2 days additional

---

## Rank 5 — Buczek Enterprises (Score: 8/10)

**Website:** https://www.buczekenterprises.com  
**Automation Method:** HTTP_GET  
**Blockers:** None  
**Recommended Priority:** HIGH  
**Cost:** Free  

### What to Automate

Monthly download and parse of Buczek Enterprises foreclosure postings for Harris, Dallas, and Tarrant Counties.

### How to Automate

1. HTTP GET to buczekenterprises.com
2. Extract county-specific notice links or PDFs
3. Download notices
4. Parse fields (address, owner, bid, date)
5. Load into AMARA-AI database

### Estimated Dev Effort

- Incremental to BDF Group + Mackie Wolf infrastructure: **1–2 days**

---

## Rank 6 — Dallas County Clerk Foreclosure Notices (Score: 7/10)

**Website:** https://www.dallascounty.org/departments/countyclerk/foreclosures.php  
**Automation Method:** PDF_PARSE  
**Blockers:** None  
**Recommended Priority:** HIGH  
**Cost:** Free  

### What to Automate

Monthly detection and download of the Dallas County Clerk's official foreclosure notice PDF, followed by structured parsing.

### How to Automate

1. **Monitor:** Monthly HTTP GET to the Dallas County Clerk foreclosure page to detect new PDF link
2. **Download:** HTTP GET to download the new monthly PDF when detected
3. **Parse:** PDF text extraction — extract all notice entries
4. **Structure:** For each entry: property address, owner name, opening bid, sale date, trustee firm
5. **Validation:** Cross-reference entry count against prior month for anomaly detection
6. **Load:** Insert into AMARA-AI database with county clerk source attribution

### What Data You Get

| Field | Available |
|---|---|
| Property address | YES |
| Owner name | YES |
| Opening bid | YES |
| Sale date | YES |
| Trustee firm | YES |
| Complete county coverage | YES — all firms |

### Blockers

- **None** — public access, no login
- **Monthly update cycle** — new data only once per month (vs. daily for PropertyRadar/ATTOM)

### Estimated Dev Effort

- HTTP monitor for new PDF detection: **0.5 day**
- PDF download automation: **0.5 day**
- PDF parser (may differ from trustee firm PDFs): **2 days**
- Validation and loading: **0.5 day**
- **Total:** 3.5 days

---

## Rank 7 — Tarrant County Clerk Foreclosure Notices (Score: 7/10)

**Website:** https://www.tarrantcounty.com/en/court-records/county-clerk.html  
**Automation Method:** PDF_PARSE  
**Blockers:** None  
**Recommended Priority:** HIGH  
**Cost:** Free  

Same automation approach as Dallas County Clerk. Reuses the county clerk PDF parsing infrastructure with minor configuration changes for Tarrant County's specific page structure and PDF format.

**Estimated Dev Effort:** 1–2 days incremental (reusing Dallas County Clerk infrastructure)

---

## Rank 8 — LOGS.org (Score: 7/10)

**Website:** https://logs.org  
**Automation Method:** HTTP_GET + PDF_PARSE  
**Blockers:** None  
**Recommended Priority:** HIGH  
**Cost:** Free  

### What to Automate

Monthly scrape of LOGS.org for Texas county foreclosure notices not covered by the primary trustee firm sites (Shapiro Schwartz LLP and other LOGS.org posting firms).

### How to Automate

1. HTTP GET to logs.org with county filter (Harris, Dallas, Tarrant)
2. Extract notice listings or PDF download links
3. Download PDFs or scrape notice data from HTML
4. Parse key fields
5. Deduplicate against BDF Group / Mackie Wolf records to identify unique LOGS.org-only listings

**Estimated Dev Effort:** 2 days (HTTP scraper + parser + deduplication logic)

---

## Rank 9 — Harris County District Clerk (Score: 6/10)

**Website:** https://www.hcdistrictclerk.com  
**Automation Method:** PDF_PARSE  
**Blockers:** None (but limited search interface)  
**Recommended Priority:** MEDIUM  
**Cost:** Free  

### What to Automate

The Harris County District Clerk is best used as a **verification source** rather than a primary extraction target. The site's search interface (by name or case number) is not well-suited for bulk extraction, but PDFs are available once specific cases are identified.

### How to Automate

Best approached by name-based lookups seeded from BDF Group / Mackie Wolf data:
1. Take owner names from BDF Group / Mackie Wolf PDFs
2. Query Harris County District Clerk by name to pull the official court filing
3. Download the official court filing PDF as the authoritative record
4. Store alongside the trustee firm record for legal accuracy

**Estimated Dev Effort:** 2–3 days (name-based lookup automation + PDF download)

---

## Sources NOT Recommended for Automation (Low ROI)

| Source | Why Not | Alternative |
|---|---|---|
| Courthouse Steps (all 3) | Physical only — no online presence | Hire local courthouse buyer / reporter |
| Foreclosure.com | JS-heavy + subscription wall; redundant with PropertyRadar | Use PropertyRadar API instead |
| RealtyTrac | JS-heavy + subscription wall; redundant | Use PropertyRadar API instead |
| BiggerPockets | UNVERIFIED URL, community data — not real-time | Use primary sources |
| Texas Comptroller | Annual updates, no direct listing data | Reference only |
| TexasLoanStar.net | UNVERIFIED — limited foreclosure data likely | Skip; verify first |
| Arlington Morning News | UNVERIFIED; small local coverage | Use Tarrant County Clerk instead |

---

## Recommended Automation Rollout Order

| Phase | Source | Method | Effort | Expected Lead Volume |
|---|---|---|---|---|
| Phase 1 | BDF Group | PDF_PARSE + HTTP_GET | 4–5 days | 300–800/month (all 3 counties) |
| Phase 1 | Mackie Wolf | PDF_PARSE + HTTP_GET | 1–2 days add-on | +200–500/month |
| Phase 1 | Buczek Enterprises | HTTP_GET | 1–2 days add-on | +100–300/month |
| Phase 1 | Dallas County Clerk | PDF_PARSE | 3.5 days | +100–200/month (validation) |
| Phase 2 | Tarrant County Clerk | PDF_PARSE | 1–2 days add-on | +100–200/month (validation) |
| Phase 2 | LOGS.org | HTTP_GET + PDF_PARSE | 2 days | +50–150/month |
| Phase 3 | PropertyRadar API | API | 4–5 days | Daily refresh of all data |
| Phase 3 | ATTOM Data API | API | 6–8 days | Institutional-grade feed |

**Total Phase 1 effort:** ~10–11 days  
**Total Phase 1–2 effort:** ~13–15 days  
**Total Phase 1–3 effort:** ~23–28 days  

---

*Generated by AMARA-AI Texas Foreclosure Intel Module | Automation-Ready Sources Report | 2026-05-16*
