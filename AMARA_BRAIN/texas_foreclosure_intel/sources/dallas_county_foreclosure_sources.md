# Dallas County Foreclosure Sources — Deep Dive

**Project:** AMARA-AI Texas Foreclosure Intel Module  
**County:** Dallas County, TX  
**Market:** Dallas Metro  
**Last Updated:** 2026-05-16  
**Analyst:** AMARA-AI Automated  

---

## Overview — Dallas Market Context

Dallas County is Texas's second most populous county and home to one of the fastest-growing metro areas in the United States. The Dallas market offers significant foreclosure investment opportunities driven by a combination of high mortgage origination volume, investor speculation, and economic migration patterns.

**Key Dallas Market Facts:**
- Dallas County regularly ranks among the top Texas counties by monthly trustee-sale volume
- The market includes both urban Dallas and inner-ring suburban areas (Garland, Mesquite, Irving, DeSoto)
- High concentrations of distressed properties are found in southern and southeastern Dallas ZIP codes
- Dallas County has a well-organized official foreclosure notice system via the County Clerk
- The Dallas Morning News serves as the primary legal newspaper for required notice publications

**Courthouse Auction Location:**  
George Allen Courts Building  
**600 Commerce St, Dallas, TX 75202**  
Sales held first Tuesday of each month, 10:00 AM – 4:00 PM

**Primary Filing Office:**  
Dallas County Clerk — records all foreclosure notices and deed of trust filings as public record

**Legal Framework:** Texas Property Code Chapter 51, non-judicial foreclosure, 21-day minimum notice requirement

---

## Official County Sources

### 1. Dallas County Clerk – Deed of Trust Foreclosure Notices
**Website:** https://www.dallascounty.org  
**Direct Foreclosure URL:** https://www.dallascounty.org/departments/countyclerk/foreclosures.php  
**Source Type:** Official County Source  
**Verification Status:** VERIFIED  

The Dallas County Clerk's Office is the official repository for all foreclosure notice filings in Dallas County. This is the **single most important primary source** for Dallas County foreclosure intelligence. The county posts monthly notice lists with downloadable PDFs containing property addresses, owner names, opening bids, and sale dates.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES |
| Opening Bids | YES |
| Unpaid Balance | NO |
| PDFs | YES — downloadable |
| Auction Dates | YES |
| Search by County | YES |
| Search by ZIP | NO |

**Update Frequency:** Monthly — notices filed approximately 20–25 days before the first Tuesday sale  
**Automation Score:** 7/10  
**Lead Quality Score:** 9/10  
**Investor Intel Score:** 9/10  

**Automation Method:** PDF_PARSE  
**Automation Notes:** PDF documents are published monthly. A scheduled downloader can retrieve the monthly PDF as soon as it is posted, then a parser extracts addresses, owner names, and opening bids. This is a top-priority automation target because the data is free, complete, and directly from the official source.  
**Blockers:** None — PDFs are publicly accessible without login

**Action Steps:**
1. Set up a monthly HTTP monitor for the foreclosure page to detect when the new month's PDF is posted
2. Download the PDF automatically
3. Parse key fields: property address, borrower name, trustee name, opening bid, sale date
4. Load into AMARA-AI lead database

---

### 2. Dallas Central Appraisal District (DCAD)
**Website:** https://www.dallascad.org  
**Source Type:** Official County Source  
**Verification Status:** VERIFIED  

DCAD provides property ownership and valuation data for all Dallas County parcels. Used primarily for skip-tracing (finding owner mailing addresses) and property value enrichment. Not a direct foreclosure listing source.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES (legal owner) |
| Assessed Value | YES |
| Property Characteristics | YES |
| Search by Address | YES |
| Search by Owner | YES |

**Update Frequency:** Continuous  
**Automation Score:** 6/10  
**Lead Quality Score:** 5/10 (enrichment, not foreclosure-specific)  
**Investor Intel Score:** 5/10  

**Use Case:** After pulling Dallas County Clerk foreclosure notices, cross-reference each property address against DCAD to obtain owner mailing address, assessed value, and property characteristics for pre-foreclosure outreach.

---

### 3. Dallas Courthouse Steps – George Allen Courts Building
**Location:** 600 Commerce St, Dallas, TX 75202  
**Source Type:** Official County Source (Physical Auction)  
**Verification Status:** VERIFIED  

The actual trustee sale takes place at the George Allen Courts Building on the first Tuesday of each month. This is a physical auction with no live online feed. Winning bidders must pay in full on the day of the sale (cashier's check required). Properties are sold as-is.

**Automation Score:** 2/10 — Physical only, no online presence  
**Lead Quality Score:** 9/10 — High-value wholesale opportunity  
**Investor Intel Score:** 7/10 — Attending provides real-time competitive intelligence  

**Action Steps:** Establish a relationship with a local Dallas real estate attorney or courthouse buyer to obtain real-time attendance and bid data for integration into AMARA-AI.

---

## Trustee Law Firms

The following firms are the dominant substitute trustees for Dallas County foreclosures. Their public posting websites are primary automation targets.

---

### 4. Barrett Daffin Frappier Turner & Engel LLP (BDF Group) – Dallas
**Website:** https://www.bdfgroup.com  
**Foreclosure Postings URL:** https://www.bdfgroup.com/foreclosure-posting/  
**Source Type:** Trustee Law Firm  
**Verification Status:** VERIFIED  

BDF Group is the dominant trustee law firm across all three major Texas counties including Dallas. The firm's website provides county-searchable PDF downloads of all upcoming trustee-sale notices. Dallas County PDFs include property addresses, owner names, opening bids, and sale dates.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES |
| Opening Bids | YES |
| PDFs | YES — downloadable |
| Auction Dates | YES |
| Search by County | YES |

**Update Frequency:** Monthly  
**Automation Score:** 8/10 | **Lead Quality Score:** 9/10 | **Investor Intel Score:** 9/10  
**Automation Method:** HTTP_GET + PDF_PARSE  
**Blockers:** None significant  
**Recommended Priority:** HIGH

---

### 5. Mackie Wolf Zientz & Mann PC – Dallas
**Website:** https://www.mwzmlaw.com  
**Foreclosure Postings URL:** https://www.mwzmlaw.com/foreclosure-postings/  
**Source Type:** Trustee Law Firm  
**Verification Status:** VERIFIED  

Second major trustee firm active in Dallas County. Website provides county-searchable PDF postings. Good complement to BDF Group as different lenders use different trustee firms, so combining both sources maximizes lead coverage.

**Update Frequency:** Monthly  
**Automation Score:** 8/10 | **Lead Quality Score:** 9/10 | **Investor Intel Score:** 8/10  
**Automation Method:** HTTP_GET + PDF_PARSE  
**Blockers:** None significant  
**Recommended Priority:** HIGH

---

### 6. Buczek Enterprises – Dallas Postings
**Website:** https://www.buczekenterprises.com  
**Source Type:** Trustee Law Firm  
**Verification Status:** VERIFIED  

Multi-county Texas substitute trustee firm with active Dallas County postings. PDFs available for download.

**Update Frequency:** Monthly  
**Automation Score:** 8/10 | **Lead Quality Score:** 9/10 | **Investor Intel Score:** 8/10  
**Automation Method:** HTTP_GET  
**Recommended Priority:** HIGH

---

### 7. LOGS.org – Legal Notice Platform (Dallas County)
**Website:** https://logs.org  
**Source Type:** Public Notice Website / Trustee Firm Platform  
**Verification Status:** VERIFIED  

LOGS.org aggregates trustee-sale notices from multiple Texas law firms and is searchable by county. Dallas County notices are included. PDFs downloadable. Serves as both a direct trustee posting site and a multi-firm aggregator.

**Update Frequency:** Monthly  
**Automation Score:** 7/10 | **Lead Quality Score:** 8/10 | **Investor Intel Score:** 7/10  
**Automation Method:** HTTP_GET + PDF_PARSE  
**Recommended Priority:** HIGH

---

## Foreclosure Platforms

---

### 8. PropertyRadar – Dallas County
**Website:** https://www.propertyradar.com  
**Source Type:** Foreclosure Platform  
**Verification Status:** VERIFIED  

PropertyRadar provides the highest-quality automated foreclosure monitoring for Dallas County. Daily updates, full address and owner data, opening bids, unpaid balances, trustee information, and API access for enterprise subscribers.

**Update Frequency:** Daily  
**Automation Score:** 9/10 | **Lead Quality Score:** 9/10 | **Investor Intel Score:** 9/10  
**Automation Method:** API  
**Blockers:** SUBSCRIPTION_WALL  
**Recommended Priority:** HIGH

---

### 9. Foreclosure.com – Dallas TX
**Website:** https://www.foreclosure.com  
**Listing URL:** https://www.foreclosure.com/foreclosure/tx/dallas/  
**Source Type:** Foreclosure Platform  
**Verification Status:** VERIFIED  

Aggregates Dallas County public notice data with addresses and estimated values. Daily updates. Subscription required for full access.

**Automation Score:** 7/10 | **Lead Quality Score:** 8/10 | **Investor Intel Score:** 7/10  
**Automation Method:** PLAYWRIGHT  
**Blockers:** SUBSCRIPTION_WALL, JS_HEAVY

---

## Tax Sale Sources

---

### 10. Dallas County Tax Office – Delinquent Tax Sales
**Website:** https://www.dallascountytax.com  
**Source Type:** Tax Sale Source  
**Verification Status:** VERIFIED  

Dallas County tax delinquent property auction listings. Opening bids reflect the amount of delinquent tax liens. Properties include residential, commercial, and vacant land. Tax sales are a separate pipeline from deed-of-trust foreclosures and can yield deeply discounted acquisitions.

**Update Frequency:** Per-sale cycle  
**Automation Score:** 6/10 | **Lead Quality Score:** 7/10 | **Investor Intel Score:** 6/10

---

## Legal Newspapers

### 11. Dallas Morning News – Public Notices
**Website:** https://www.dallasnews.com  
**Public Notices URL:** https://www.dallasnews.com/public-notices/  
**Source Type:** Legal Newspaper  
**Verification Status:** VERIFIED  

The Dallas Morning News is the state-designated qualified newspaper for Dallas County public notice requirements under Texas law. Trustee sale notices are published at least 21 days before the first Tuesday sale date. The online public notice database is searchable and provides a cross-reference for verifying notice publication.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES |
| Opening Bids | NO |
| PDFs | NO |
| Auction Dates | YES |

**Update Frequency:** Weekly  
**Automation Score:** 5/10 | **Lead Quality Score:** 7/10 | **Investor Intel Score:** 5/10  

**Note:** Primary value is as a verification source and early-notice source — notices appear here at the same time as county clerk filings. Not recommended as a primary automation target due to newspaper website structure.

---

### 12. Texas HOA Foreclosure Filings – Dallas
**Website:** https://www.dallascounty.org/departments/countyclerk/  
**Source Type:** HOA Foreclosure Source  
**Verification Status:** UNVERIFIED  

HOA foreclosure notices filed with the Dallas County Clerk. Governed by Texas Property Code Chapter 209 for residential HOAs. These represent a separate pipeline of distressed properties, often at lower price points than deed-of-trust foreclosures. Requires manual verification to confirm the specific filing system and public access to HOA foreclosure notices.

**Automation Score:** 6/10 | **Lead Quality Score:** 7/10 | **Investor Intel Score:** 5/10  
**Status:** Requires manual confirmation before automation

---

## Automation Recommendations

### Priority 1 — Automate First

| Source | Rationale | Method | Effort |
|---|---|---|---|
| Dallas County Clerk (dallascounty.org/foreclosures) | Free, official, complete data, PDFs | PDF_PARSE | 2–3 days |
| BDF Group (bdfgroup.com) | Largest private volume, no login, PDFs | HTTP_GET + PDF_PARSE | 2–3 days |
| Mackie Wolf (mwzmlaw.com) | Second-largest volume, complementary to BDF | HTTP_GET + PDF_PARSE | 2–3 days |
| Buczek Enterprises | Multi-county, public postings | HTTP_GET | 1–2 days |
| LOGS.org | Aggregates multiple firms, PDF support | HTTP_GET + PDF_PARSE | 2 days |

### Priority 2 — Automate with Subscription

| Source | Rationale | Method |
|---|---|---|
| PropertyRadar | Best data quality, daily updates, API | API |
| ATTOM Data | Institutional grade, full feed | API |

### Priority 3 — Manual / Cross-Reference Only

| Source | Why |
|---|---|
| Courthouse Steps | Physical only |
| Dallas Morning News | Cross-reference / verification |
| Foreclosure.com | Redundant if PropertyRadar active |

---

## Data Gaps

1. **HOA Foreclosure Notices** — Confirm whether HOA foreclosure notices are separately searchable in the Dallas County Clerk system, and whether they are included in the existing foreclosures.php page or filed separately.

2. **Dallas County Clerk PDF Schema** — Document the exact field layout of the Dallas County Clerk monthly foreclosure PDF to build a reliable parser. The county may use a consistent template or vary by batch.

3. **GovEase Dallas Participation** — Determine whether Dallas County uses GovEase or another online platform for tax delinquent auctions, or whether all tax sales occur physically.

4. **BDF Group Dallas vs. Harris PDF Format** — Determine whether BDF Group uses the same PDF schema for Dallas County notices as for Harris County, or whether separate parsers are needed.

5. **DCAD Bulk Access** — Investigate whether DCAD provides bulk property data downloads or an API to support mass skip-tracing operations for pre-foreclosure outreach.

6. **Legal Newspaper Automation** — Assess whether the Dallas Morning News public notice database is automatable via structured HTTP requests or requires PLAYWRIGHT due to JavaScript rendering.

---

*Generated by AMARA-AI Texas Foreclosure Intel Module | Dallas County Deep Dive | 2026-05-16*
