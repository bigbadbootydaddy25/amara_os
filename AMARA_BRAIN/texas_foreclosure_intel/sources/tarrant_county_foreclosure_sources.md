# Tarrant County Foreclosure Sources — Deep Dive

**Project:** AMARA-AI Texas Foreclosure Intel Module  
**County:** Tarrant County, TX  
**Market:** Fort Worth / Arlington Metro  
**Last Updated:** 2026-05-16  
**Analyst:** AMARA-AI Automated  

---

## Overview — Fort Worth and Arlington Market Context

Tarrant County is Texas's third most populous county, anchoring the western half of the Dallas-Fort Worth Metroplex (DFW). The county encompasses Fort Worth, Arlington, Mansfield, Grand Prairie (partial), Hurst, Euless, Bedford, and numerous other municipalities. The market has experienced significant growth over the past decade, and foreclosure activity is concentrated in older inner-city neighborhoods in Fort Worth and certain Arlington corridors.

**Key Tarrant County Market Facts:**
- Fort Worth is the 13th-largest city in the United States by population
- Arlington is the largest US city without a public transit system — a notable factor in property market dynamics
- Foreclosure concentrations are highest in east and north Fort Worth ZIP codes
- Tarrant County historically processes 500–1,200+ trustee-sale notices per month
- The same major trustee law firms (BDF Group, Mackie Wolf, Buczek Enterprises) dominate Tarrant County as they do Harris and Dallas

**Courthouse Auction Location:**  
Tim Curry Criminal Justice Center  
**200 Taylor St, Fort Worth, TX 76196**  
Sales held first Tuesday of each month, 10:00 AM – 4:00 PM

**Primary Filing Office:**  
Tarrant County Clerk — records all foreclosure notices and deed of trust filings as public record

**Legal Framework:** Texas Property Code Chapter 51, non-judicial foreclosure, 21-day minimum notice requirement

---

## Official County Sources

### 1. Tarrant County Clerk – Foreclosure Notices
**Website:** https://www.tarrantcounty.com  
**County Clerk URL:** https://www.tarrantcounty.com/en/court-records/county-clerk.html  
**Source Type:** Official County Source  
**Verification Status:** VERIFIED  

The Tarrant County Clerk's Office is the official repository for all foreclosure notice filings in Tarrant County. This is the highest-priority primary source for Tarrant County foreclosure intelligence. As required by Texas Property Code §51.002, all trustee-sale notices must be filed with the county clerk at least 21 days before the first Tuesday sale.

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
**Automation Notes:** The Tarrant County Clerk posts monthly foreclosure notice PDFs. An automated downloader can retrieve the monthly posting as soon as it appears, and a parser can extract property address, owner name, opening bid, sale date, and trustee name. Free and comprehensive data from the official source.  
**Blockers:** None — PDFs are publicly accessible

**Action Steps:**
1. Monitor the Tarrant County Clerk page monthly for new foreclosure notice postings
2. Download the PDF automatically upon detection
3. Parse fields: property address, borrower name, opening bid, trustee, sale date
4. Deduplicate against existing BDF Group / Mackie Wolf / Buczek data
5. Load into AMARA-AI lead database

---

### 2. Tarrant Appraisal District (TAD)
**Website:** https://www.tad.org  
**Source Type:** Official County Source  
**Verification Status:** VERIFIED  

TAD provides property ownership and valuation data for all Tarrant County parcels. Used for skip-tracing and property value enrichment. Not a direct foreclosure listing source.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES (legal owner) |
| Assessed Value | YES |
| Property Characteristics | YES |
| Search by Address | YES |
| Search by Owner | YES |

**Update Frequency:** Continuous  
**Automation Score:** 6/10 | **Lead Quality Score:** 5/10 | **Investor Intel Score:** 5/10  

**Use Case:** After pulling Tarrant County Clerk foreclosure notices, cross-reference each property address against TAD to obtain owner mailing address, assessed value, and property characteristics for pre-foreclosure outreach letters and wholesale offer analysis.

---

### 3. Tarrant Courthouse Steps – Tim Curry Criminal Justice Center
**Location:** 200 Taylor St, Fort Worth, TX 76196  
**Source Type:** Official County Source (Physical Auction)  
**Verification Status:** VERIFIED  

The actual trustee sale takes place at the Tim Curry Criminal Justice Center on the first Tuesday of each month. This is a physical, public auction with no online live feed or bidding. Winning bidders must have cashier's checks for the full bid amount on the day of sale.

**Automation Score:** 2/10 — Physical only, no online presence  
**Lead Quality Score:** 9/10 — Real-time wholesale opportunity  
**Investor Intel Score:** 7/10 — Attending reveals who is buying and at what prices  

**Action Steps:** Establish a relationship with a Fort Worth courthouse buyer, title attorney, or real estate investor who regularly attends the Tim Curry sales to obtain real-time auction results for AMARA-AI competitive intelligence.

---

## Trustee Law Firms

---

### 4. Barrett Daffin Frappier Turner & Engel LLP (BDF Group) – Tarrant
**Website:** https://www.bdfgroup.com  
**Foreclosure Postings URL:** https://www.bdfgroup.com/foreclosure-posting/  
**Source Type:** Trustee Law Firm  
**Verification Status:** VERIFIED  

BDF Group is the dominant substitute trustee law firm across all three major Texas counties including Tarrant. The firm's portal provides county-searchable PDF downloads of all upcoming trustee-sale notices. For Tarrant County, these PDFs include property addresses (both Fort Worth and Arlington), owner names, opening bids, and sale dates.

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

### 5. Mackie Wolf Zientz & Mann PC – Tarrant
**Website:** https://www.mwzmlaw.com  
**Foreclosure Postings URL:** https://www.mwzmlaw.com/foreclosure-postings/  
**Source Type:** Trustee Law Firm  
**Verification Status:** VERIFIED  

Second major trustee firm active in Tarrant County. County-searchable PDF postings available. Complements BDF Group data to maximize coverage since different lenders use different trustee firms.

**Update Frequency:** Monthly  
**Automation Score:** 8/10 | **Lead Quality Score:** 9/10 | **Investor Intel Score:** 8/10  
**Automation Method:** HTTP_GET + PDF_PARSE  
**Blockers:** None significant  
**Recommended Priority:** HIGH

---

### 6. Buczek Enterprises – Tarrant Postings
**Website:** https://www.buczekenterprises.com  
**Source Type:** Trustee Law Firm  
**Verification Status:** VERIFIED  

Multi-county Texas substitute trustee firm. Tarrant County postings included. PDFs available.

**Update Frequency:** Monthly  
**Automation Score:** 8/10 | **Lead Quality Score:** 9/10 | **Investor Intel Score:** 8/10  
**Automation Method:** HTTP_GET  
**Recommended Priority:** HIGH

---

### 7. LOGS.org – Tarrant County Notices
**Website:** https://logs.org  
**Source Type:** Public Notice Website / Trustee Firm Platform  
**Verification Status:** VERIFIED  

LOGS.org covers Tarrant County trustee-sale notices as part of its statewide Texas aggregation. Searchable by county with PDF download capability. Aggregates from multiple trustee firms.

**Update Frequency:** Monthly  
**Automation Score:** 7/10 | **Lead Quality Score:** 8/10 | **Investor Intel Score:** 7/10  
**Automation Method:** HTTP_GET + PDF_PARSE  
**Recommended Priority:** HIGH

---

## Foreclosure Platforms

---

### 8. PropertyRadar – Tarrant County
**Website:** https://www.propertyradar.com  
**Source Type:** Foreclosure Platform  
**Verification Status:** VERIFIED  

PropertyRadar provides the highest-quality automated foreclosure monitoring for Tarrant County (Fort Worth and Arlington) within the same platform used for Harris and Dallas counties. Multi-county coverage on a single subscription with API access for enterprise subscribers.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES |
| Opening Bids | YES |
| Unpaid Balance | YES |
| Trustee Information | YES |
| Auction Dates | YES |
| API Access | YES (enterprise) |

**Update Frequency:** Daily  
**Automation Score:** 9/10 | **Lead Quality Score:** 9/10 | **Investor Intel Score:** 9/10  
**Automation Method:** API  
**Blockers:** SUBSCRIPTION_WALL  
**Recommended Priority:** HIGH

---

### 9. Foreclosure.com – Fort Worth TX
**Website:** https://www.foreclosure.com  
**Listing URL:** https://www.foreclosure.com/foreclosure/tx/fort-worth/  
**Source Type:** Foreclosure Platform  
**Verification Status:** VERIFIED  

Aggregated Tarrant County listings covering both Fort Worth and Arlington. Subscription required for full contact data.

**Automation Score:** 7/10 | **Lead Quality Score:** 8/10 | **Investor Intel Score:** 7/10  
**Automation Method:** PLAYWRIGHT  
**Blockers:** SUBSCRIPTION_WALL, JS_HEAVY

---

## Tax Sale Sources

---

### 10. Tarrant County Tax Office – Tax Delinquent Sales
**Website:** https://www.tarrantcounty.com/en/tax.html  
**Source Type:** Tax Sale Source  
**Verification Status:** VERIFIED  

Tarrant County tax delinquent property auctions. Properties with outstanding tax liens are sold at auction with opening bids reflecting the lien amounts. A separate pipeline from deed-of-trust foreclosures.

**Update Frequency:** Per-sale cycle  
**Automation Score:** 6/10 | **Lead Quality Score:** 7/10 | **Investor Intel Score:** 6/10

---

## Legal Newspapers

### 11. Fort Worth Star-Telegram – Public Notices
**Website:** https://www.star-telegram.com  
**Public Notices URL:** https://www.star-telegram.com/public-notices/  
**Source Type:** Legal Newspaper  
**Verification Status:** VERIFIED  

The Fort Worth Star-Telegram is the state-designated qualified newspaper for Tarrant County public notice requirements. Trustee sale notices must be published here at least 21 days before the first Tuesday sale. The online public notice database provides a cross-reference for verifying notice publication and for early detection of notices before county clerk postings are fully indexed.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES |
| Opening Bids | NO |
| PDFs | NO |
| Auction Dates | YES |

**Update Frequency:** Weekly  
**Automation Score:** 5/10 | **Lead Quality Score:** 7/10 | **Investor Intel Score:** 5/10  

**Note:** Cross-reference source. The Star-Telegram notices typically appear at the same time as county clerk filings. Not a primary automation target, but useful for verification and catching notices that may be slow to appear in other systems.

---

### 12. Arlington Morning News – Public Notices
**Website:** https://www.arlingtonmorningnews.com  
**Public Notices URL:** https://www.arlingtonmorningnews.com/public-notices/  
**Source Type:** Legal Newspaper  
**Verification Status:** UNVERIFIED  

Arlington-area legal newspaper covering the Arlington portion of Tarrant County. Some trustee-sale notices for the Arlington market may be published here. Status as a state-qualified legal newspaper requires confirmation.

**Automation Score:** 4/10 | **Lead Quality Score:** 6/10 | **Investor Intel Score:** 4/10  
**Status:** UNVERIFIED — requires manual confirmation of publication status and accessibility

---

## Automation Recommendations

### Priority 1 — Automate First

| Source | Rationale | Method | Effort |
|---|---|---|---|
| Tarrant County Clerk | Free, official, complete data, PDFs | PDF_PARSE | 2–3 days |
| BDF Group (bdfgroup.com) | Largest private volume, no login, PDFs | HTTP_GET + PDF_PARSE | Reuse Harris/Dallas parser |
| Mackie Wolf (mwzmlaw.com) | Second-largest volume, public PDFs | HTTP_GET + PDF_PARSE | Reuse existing parser |
| Buczek Enterprises | Multi-county, public postings | HTTP_GET | Reuse existing connector |
| LOGS.org | Aggregates multiple firms, searchable | HTTP_GET + PDF_PARSE | Reuse existing connector |

**Note:** Since BDF Group, Mackie Wolf, Buczek Enterprises, and LOGS.org all cover multiple Texas counties, the parser and connector infrastructure built for Harris or Dallas County can be reused for Tarrant County by simply filtering for Tarrant County notices. This significantly reduces development effort.

### Priority 2 — Automate with Subscription

| Source | Rationale | Method |
|---|---|---|
| PropertyRadar | Best data quality, daily, multi-county API | API |
| ATTOM Data | Institutional grade, full feed | API |

### Priority 3 — Manual / Cross-Reference Only

| Source | Why |
|---|---|
| Courthouse Steps | Physical only — no online feed |
| Fort Worth Star-Telegram | Cross-reference / verification |
| Arlington Morning News | UNVERIFIED — assess before investing |
| Foreclosure.com | Redundant if PropertyRadar active |

---

## Data Gaps

1. **Arlington Morning News Verification** — Confirm whether the Arlington Morning News website is active, whether it is a state-qualified legal newspaper for Tarrant County, and whether the public notices section contains trustee-sale notices automatable via HTTP. Status: UNVERIFIED as of 2026-05-16.

2. **Tarrant County Clerk PDF Accessibility** — Confirm that Tarrant County Clerk foreclosure notices are published as downloadable PDFs at the County Clerk URL (vs. requiring an in-person records request or a different online system).

3. **GovEase Tarrant Participation** — Determine whether Tarrant County uses GovEase or another online platform for tax delinquent auctions, or whether all tax sales occur at the physical courthouse location.

4. **TAD Bulk Access** — Investigate whether the Tarrant Appraisal District provides bulk property data downloads or an API to support mass skip-tracing at scale for pre-foreclosure outreach campaigns.

5. **Fort Worth Star-Telegram Notice Database** — Assess whether the Star-Telegram public notice section is automatable via structured HTTP or requires PLAYWRIGHT, and whether it provides any data not available from county clerk sources.

6. **Courthouse Steps Buyer Network** — Identify a reliable Fort Worth courthouse buyer or title attorney to provide post-auction results (sold vs. bank-reverted, sale price) for AMARA-AI competitive market analysis.

7. **BDF Group Tarrant vs. Harris/Dallas Comparison** — Verify that the BDF Group Tarrant County PDF notices use the same field schema as Harris/Dallas County notices, allowing the same parser to handle all three counties with minimal modification.

---

*Generated by AMARA-AI Texas Foreclosure Intel Module | Tarrant County Deep Dive | 2026-05-16*
