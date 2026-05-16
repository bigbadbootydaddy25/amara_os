# Harris County Foreclosure Sources — Deep Dive

**Project:** AMARA-AI Texas Foreclosure Intel Module  
**County:** Harris County, TX  
**Market:** Houston Metro  
**Last Updated:** 2026-05-16  
**Analyst:** AMARA-AI Automated  

---

## Overview — Houston Market Context

Harris County is the **most populous county in Texas** and the third most populous in the United States, with over 4.7 million residents. The Houston metro area consistently ranks among the top 5 foreclosure markets in the nation by volume, making it a primary target for all three investor strategies: wholesale acquisition, pre-foreclosure outreach, and institutional / hedge-fund tracking.

**Key Houston Market Facts:**
- Historically 1,000–2,500+ trustee-sale postings per month (volume varies with mortgage market cycles)
- Major foreclosure trustee firms process the bulk of postings, creating highly concentrated data sources
- The Houston market has significant concentrations of distressed properties in northeast and southeast ZIP codes
- Harris County has no right of first refusal and no post-sale redemption for deed-of-trust foreclosures
- Texas Property Code Chapter 51 governs all non-judicial foreclosure sales

**Courthouse Auction Location:**  
Harris County Family Law Center / Civil Courthouse  
**201 Caroline St, Houston, TX 77002**  
Sales held first Tuesday of each month, 10:00 AM – 4:00 PM

**Primary Filing Office:**  
Harris County District Clerk — records all foreclosure notices as public filings

---

## Official County Sources

### 1. Harris County District Clerk – Official Notices
**Website:** https://www.hcdistrictclerk.com  
**Source Type:** Official County Source  
**Verification Status:** VERIFIED  

The Harris County District Clerk is the primary legal repository for all foreclosure-related court filings in Harris County. Trustee-sale notices are filed here under Texas Property Code §51.002 at least 21 days before the scheduled sale date.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES |
| Opening Bids | NO |
| Unpaid Balance | NO |
| PDFs | YES (for many filings) |
| Auction Dates | YES |
| Search by County | YES |
| Search by ZIP | NO |

**Update Frequency:** Monthly, with notices filed approximately 20–25 days before the first Tuesday sale  
**Automation Score:** 6/10  
**Lead Quality Score:** 8/10  
**Investor Intel Score:** 7/10  

**Notes:** This is the authoritative primary source for Harris County. PDFs are available for some filings. Search functionality is by name or case number; batch downloading requires scripting. Best used as a verification source and combined with trustee firm postings for complete data.

---

### 2. Harris County Appraisal District (HCAD)
**Website:** https://www.hcad.org  
**Direct Records URL:** https://www.hcad.org/records/real-property/  
**Source Type:** Official County Source  
**Verification Status:** VERIFIED  

HCAD is not a foreclosure listing source, but it is an essential **skip-tracing and enrichment** resource. Every property in Harris County has an HCAD record containing the legal owner name, mailing address, assessed value, and property characteristics.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES (legal owner) |
| Opening Bids | NO |
| Assessed Value | YES |
| Search by Address | YES |
| Search by Owner | YES |

**Automation Score:** 7/10  
**Lead Quality Score:** 6/10 (enrichment, not foreclosure-specific)  
**Investor Intel Score:** 5/10  

**Use Case:** Cross-reference foreclosure notices with HCAD to obtain owner mailing addresses for pre-foreclosure outreach campaigns.

---

### 3. Texas Comptroller – Local Property Tax Sales
**Website:** https://comptroller.texas.gov/taxes/property-tax/  
**Source Type:** Official County Source  
**Verification Status:** VERIFIED  

State-level resource linking to county appraisal districts and tax offices. Not a direct foreclosure listing source; used as a reference for tax sale procedures and links.

**Automation Score:** 3/10 | **Lead Quality Score:** 5/10 | **Investor Intel Score:** 4/10

---

## Trustee Law Firms

The following firms are the primary **substitute trustees** conducting foreclosure sales in Harris County. Under Texas law, the lender appoints a substitute trustee who posts the sale notices, files with the county clerk, and conducts the auction. These firms post their sale notices publicly on their websites, making them some of the highest-value automation targets.

---

### 4. Barrett Daffin Frappier Turner & Engel LLP (BDF Group)
**Website:** https://www.bdfgroup.com  
**Foreclosure Postings URL:** https://www.bdfgroup.com/foreclosure-posting/  
**Source Type:** Trustee Law Firm  
**Verification Status:** VERIFIED  

BDF Group is widely considered the **largest Texas foreclosure trustee law firm** by volume. The firm handles thousands of trustee sales per month across Harris, Dallas, and Tarrant counties, as well as other Texas counties. Their online posting portal provides downloadable PDFs searchable by county, making it one of the highest-value automation targets in the entire Texas market.

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

**Update Frequency:** Monthly — typically updated 20–25 days before the first Tuesday sale  
**Automation Score:** 8/10  
**Lead Quality Score:** 9/10  
**Investor Intel Score:** 9/10  

**Automation Method:** HTTP_GET + PDF_PARSE  
**Automation Notes:** County-specific PDF downloads are accessible without login. PDF parsing required to extract structured data (address, owner, opening bid, sale date, trustee). Highly recommended as a first automation target.  
**Blockers:** None significant — PDFs are public and downloadable

---

### 5. Mackie Wolf Zientz & Mann PC
**Website:** https://www.mwzmlaw.com  
**Foreclosure Postings URL:** https://www.mwzmlaw.com/foreclosure-postings/  
**Source Type:** Trustee Law Firm  
**Verification Status:** VERIFIED  

Mackie Wolf is a major Texas foreclosure law firm with extensive Harris County postings. Like BDF Group, the firm posts sale notices publicly on its website with downloadable PDFs. Covers Harris, Dallas, Tarrant, and other Texas counties.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES |
| Opening Bids | YES |
| PDFs | YES — downloadable |
| Auction Dates | YES |
| Search by County | YES |

**Update Frequency:** Monthly  
**Automation Score:** 8/10  
**Lead Quality Score:** 9/10  
**Investor Intel Score:** 8/10  

**Automation Method:** HTTP_GET + PDF_PARSE  
**Automation Notes:** Similar structure to BDF Group. County-level PDF filtering available. Good PDF parse target.  
**Blockers:** None significant

---

### 6. Buczek Enterprises
**Website:** https://www.buczekenterprises.com  
**Foreclosure Postings URL:** https://www.buczekenterprises.com/  
**Source Type:** Trustee Law Firm  
**Verification Status:** VERIFIED  

Buczek Enterprises is a major Texas substitute trustee operation handling sales across Harris, Dallas, Tarrant, and additional counties. Posts sale notices directly on the website with PDFs available for download. Active in both deed-of-trust and HOA foreclosures.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES |
| Opening Bids | YES |
| PDFs | YES |
| Auction Dates | YES |

**Update Frequency:** Monthly  
**Automation Score:** 8/10  
**Lead Quality Score:** 9/10  
**Investor Intel Score:** 8/10  

**Automation Method:** HTTP_GET  
**Blockers:** None significant

---

### 7. Shapiro Schwartz LLP / LOGS.org
**Website:** https://logs.org  
**Source Type:** Trustee Law Firm / Legal Notice Platform  
**Verification Status:** VERIFIED  

LOGS.org (Legal Online Posting Service) is a Texas-specific legal notice aggregation platform used by multiple trustee law firms including Shapiro Schwartz. Notices are searchable by county and downloadable as PDFs. Serves as both a trustee firm posting site and a cross-county aggregator.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES |
| Opening Bids | YES |
| PDFs | YES |
| Auction Dates | YES |
| Search by County | YES |
| Search by ZIP | YES |

**Update Frequency:** Monthly  
**Automation Score:** 7/10  
**Lead Quality Score:** 8/10  
**Investor Intel Score:** 8/10  

**Automation Method:** HTTP_GET + PDF_PARSE

---

## Foreclosure Platforms

These are third-party data aggregators that compile public notice data from multiple sources and present it in a searchable, often enriched format. Most require paid subscriptions for full data access.

---

### 8. PropertyRadar – Texas
**Website:** https://www.propertyradar.com  
**Source Type:** Foreclosure Platform  
**Verification Status:** VERIFIED  

PropertyRadar is the **highest-rated foreclosure intelligence platform** for Texas markets. It aggregates trustee-sale notices, enriches them with property and owner data, and provides daily updates. An API is available for enterprise subscribers, making it the top automation candidate among paid platforms.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES |
| Opening Bids | YES |
| Unpaid Balance | YES |
| Trustee Information | YES |
| Auction Dates | YES |
| Search by County | YES |
| Search by ZIP | YES |
| API Access | YES (enterprise) |

**Update Frequency:** Daily  
**Automation Score:** 9/10  
**Lead Quality Score:** 9/10  
**Investor Intel Score:** 9/10  

**Automation Method:** API  
**Blockers:** SUBSCRIPTION_WALL — requires paid subscription  
**Recommended Priority:** HIGH

---

### 9. ATTOM Data – Texas Foreclosure Feed
**Website:** https://www.attomdata.com  
**Source Type:** Foreclosure Platform  
**Verification Status:** VERIFIED  

ATTOM is the premier institutional-grade foreclosure data provider. Used by hedge funds, institutional buyers, and enterprise real estate platforms. Provides complete deed-of-trust foreclosure feeds, ownership data, AVM values, and distressed property overlays via API. Most expensive of the platforms but highest data depth.

| Data Field | Available |
|---|---|
| Property Addresses | YES |
| Owner Names | YES |
| Opening Bids | YES |
| Unpaid Balance | YES |
| PDFs | YES |
| Auction Dates | YES |
| Full API | YES |

**Update Frequency:** Daily  
**Automation Score:** 9/10  
**Lead Quality Score:** 9/10  
**Investor Intel Score:** 10/10  

**Automation Method:** API  
**Blockers:** SUBSCRIPTION_WALL — enterprise pricing  
**Recommended Priority:** HIGH

---

### 10. Foreclosure.com – Harris County
**Website:** https://www.foreclosure.com  
**Listing URL:** https://www.foreclosure.com/foreclosure/tx/houston/  
**Source Type:** Foreclosure Platform  
**Verification Status:** VERIFIED  

Aggregates Harris County public notice data with addresses and estimated values. Daily updates. Subscription required for full contact data access.

**Automation Score:** 7/10 | **Lead Quality Score:** 8/10 | **Investor Intel Score:** 7/10  
**Automation Method:** PLAYWRIGHT | **Blockers:** SUBSCRIPTION_WALL, JS_HEAVY

---

### 11. RealtyTrac – Harris County TX
**Website:** https://www.realtytrac.com  
**Listing URL:** https://www.realtytrac.com/mapsearch/#/TX/Harris-County/  
**Source Type:** Foreclosure Platform  
**Verification Status:** VERIFIED  

Aggregates NOD and trustee-sale notices. Subscription required for full data. Useful for investor activity tracking alongside PropertyRadar.

**Automation Score:** 6/10 | **Lead Quality Score:** 7/10 | **Investor Intel Score:** 7/10  
**Automation Method:** PLAYWRIGHT | **Blockers:** SUBSCRIPTION_WALL, JS_HEAVY

---

### 12. HAR.com – Foreclosure Listings
**Website:** https://www.har.com/foreclosures  
**Source Type:** Public Notice Website  
**Verification Status:** VERIFIED  

Houston Association of Realtors MLS-adjacent data with some foreclosure listings. Limited trustee-sale specifics. Good as a supplementary source but not primary.

**Automation Score:** 5/10 | **Lead Quality Score:** 6/10 | **Investor Intel Score:** 5/10

---

### 13. BiggerPockets Foreclosure Listings – Houston
**Website:** https://www.biggerpockets.com/foreclosures/tx/houston  
**Source Type:** Foreclosure Platform  
**Verification Status:** UNVERIFIED  

Community-driven listing aggregator. Less real-time than dedicated platforms. Good for market research but not a primary data source.

**Automation Score:** 4/10 | **Lead Quality Score:** 5/10 | **Investor Intel Score:** 4/10

---

## Tax Sale Sources

Tax sales (sheriff's sales for delinquent property taxes) are a distinct category from deed-of-trust foreclosures and follow different timing and procedures. However, they represent a significant pipeline of distressed property opportunities.

---

### 14. Bid4Assets – Texas Tax Sales
**Website:** https://www.bid4assets.com  
**Texas Tax Sales URL:** https://www.bid4assets.com/texastaxsales  
**Source Type:** Tax Sale Source  
**Verification Status:** VERIFIED  

Online tax deed auction platform. Harris County tax sales are listed here with opening bids shown. Properties include delinquent tax seizures.

**Automation Score:** 8/10 | **Lead Quality Score:** 7/10 | **Investor Intel Score:** 7/10  
**Automation Method:** HTTP_GET | **Blockers:** None significant

---

### 15. GovEase – Harris County Tax Sales
**Website:** https://www.govease.com  
**Source Type:** Tax Sale Source  
**Verification Status:** UNVERIFIED  

Online government auction platform used by some Texas counties for online tax sales. Harris County participation requires direct verification.

**Automation Score:** 8/10 | **Lead Quality Score:** 7/10 | **Investor Intel Score:** 7/10  
**Task Required:** Confirm whether Harris County currently lists tax sales on GovEase

---

## Legal Newspapers

Texas law requires publication of trustee sale notices in a qualified newspaper of general circulation in the county at least 21 days before the sale. For Harris County, this typically includes:

- **Houston Chronicle** — primary newspaper of record for Harris County public notices
- **Community Impact Newspaper** — local legal notice publication

**Note:** Most legal newspaper notice databases require separate subscriptions or have limited automation capability. They serve primarily as a verification and cross-reference source.

---

## Automation Recommendations

### Priority 1 — Automate First (Highest ROI)

| Source | Why Automate First | Method | Est. Dev Effort |
|---|---|---|---|
| BDF Group (bdfgroup.com) | Largest volume, public PDFs, no login | PDF_PARSE + HTTP_GET | 2–3 days |
| Mackie Wolf (mwzmlaw.com) | Second-largest volume, public PDFs | PDF_PARSE + HTTP_GET | 2–3 days |
| Buczek Enterprises | Public postings, high lead quality | HTTP_GET | 1–2 days |
| LOGS.org | Multi-county, searchable, PDFs | HTTP_GET + PDF_PARSE | 2 days |

### Priority 2 — Automate After Infrastructure Built

| Source | Why | Method | Blockers |
|---|---|---|---|
| PropertyRadar | Best data quality, API available | API | Subscription cost |
| ATTOM Data | Institutional grade, full API | API | Enterprise pricing |
| Dallas County Clerk | Official source, PDF downloads | PDF_PARSE | Requires workflow |
| Bid4Assets | Tax sale data, clean HTTP | HTTP_GET | Irregular schedule |

### Priority 3 — Manual or Low Priority

| Source | Why Manual | Notes |
|---|---|---|
| Courthouse Steps | Physical only | Local contact required |
| Foreclosure.com | JS-heavy, subscription wall | Consider PropertyRadar instead |
| RealtyTrac | Subscription wall, JS-heavy | Redundant if PropertyRadar active |
| HAR.com | Limited trustee-sale data | Supplementary only |

---

## Data Gaps and Tasks Needed

1. **GovEase Harris County Participation** — Confirm whether Harris County currently uses GovEase for online tax sales. Status: UNVERIFIED as of 2026-05-16.

2. **BiggerPockets URL Verification** — Confirm the specific Harris County foreclosure listing URL is active and contains real-time data. Status: UNVERIFIED.

3. **Texas.gov / TexasLoanStar.net** — This source has limited clear data. Requires manual investigation to determine whether it provides any unique foreclosure data not available from other sources.

4. **Legal Newspaper Subscription Access** — Determine which Harris County legal newspapers have automatable public notice databases versus subscription-gated archives.

5. **BDF Group PDF Schema Documentation** — Document the exact field layout of BDF Group county PDFs to accelerate parser development. Field positions may vary by month or trustee.

6. **HCAD API / Bulk Download** — Investigate whether HCAD provides bulk property data downloads or an API for owner lookups to support pre-foreclosure skip-tracing at scale.

7. **Courthouse Steps Contact** — Identify a local Houston real estate attorney or courthouse steps buyer who can provide real-time auction attendance reports for AMARA-AI integration.

---

*Generated by AMARA-AI Texas Foreclosure Intel Module | Harris County Deep Dive | 2026-05-16*
