# Texas Foreclosure Trustee Intelligence — Master Source Reference Guide

**Project:** AMARA-AI Texas Foreclosure Intel Module  
**Coverage:** Harris County (Houston), Dallas County (Dallas), Tarrant County (Fort Worth/Arlington)  
**Compiled:** 2026-05-16  
**Analyst:** AMARA-AI Automated Research  
**Status:** Active — Monthly review cycle

---

## Texas Foreclosure Law Preamble

### Governing Statute
Texas non-judicial foreclosure is governed primarily by **Texas Property Code Chapter 51** (Chapters 51.001 through 51.016). Unlike judicial states, Texas does not require a court order to foreclose on a deed of trust — the process is handled by a **substitute trustee** appointed by the lender and authorized under the security instrument.

### Key Legal Framework

**First Tuesday Rule:** Texas law mandates that all deed-of-trust foreclosure sales occur on the **first Tuesday of each month** between 10:00 AM and 4:00 PM. If the first Tuesday falls on a federal holiday, the sale is moved to the first Wednesday. Sales take place at the designated location in the county where the property is situated — historically the courthouse steps, or a specific area designated by the county commissioners court.

**21-Day Notice Requirement:** Under Texas Property Code §51.002(b), the trustee must:
1. Serve written notice of the proposed sale on the debtor at least 21 days before the date of sale.
2. Post written notice at the courthouse door of each county in which the property is located.
3. File a copy of the notice of sale with the county clerk.

The notice must include: the earliest time the sale will begin, the address of the property, and the date, time, and location of the sale.

**Notice Filing:** Filed with the **County Clerk** of each county where the property is located. These filings become public record and are the primary data source for all foreclosure intelligence systems.

**Redemption Rights:** Texas has **no right of redemption** for deed-of-trust (mortgage) foreclosures after the sale date. Tax sale properties have a redemption period of 2 years (homesteads/agricultural) or 180 days (other properties).

**HOA Foreclosures:** Texas Property Code Chapter 209 governs residential HOA foreclosures, which follow a separate process and may be filed through district courts or non-judicially depending on the HOA's authority.

**Legal Newspaper Requirement:** Texas law requires that foreclosure notices be posted in a legally designated newspaper of general circulation in the county at least 21 days before the sale date.

### Auction Locations by County
| County | Designated Auction Location |
|--------|----------------------------|
| Harris County | Harris County Family Law Center, 201 Caroline St, Houston, TX 77002 |
| Dallas County | George Allen Courts Building, 600 Commerce St, Dallas, TX 75202 |
| Tarrant County | Tim Curry Criminal Justice Center, 200 Taylor St, Fort Worth, TX 76196 |

---

## Master Source Table — All Counties

### Harris County TX (Houston Metro)

| Field | Detail |
|-------|--------|
| **County** | Harris County TX |
| **Market** | Houston |
| **Auction Location** | 201 Caroline St, Houston, TX 77002 |
| **First Tuesday Sale** | Monthly |

#### Harris County Sources

| Trustee/Source Name | Website | Source Type | Addresses Shown | Owner Names | Opening Bids | PDFs Downloadable | Auction Dates Public | Update Frequency | Automation Score | Lead Quality Score | Investor Intel Score | Verification Status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Harris County District Clerk – Official Notices | hcdistrictclerk.com | Official County Source | YES | YES | NO | YES | YES | Monthly (~20 days prior) | 6 | 8 | 7 | VERIFIED | Official court records. Foreclosure notices filed here. Search by name or case number. First-Tuesday sales. |
| Harris County Appraisal District (HCAD) | hcad.org | Official County Source | YES | YES | NO | NO | NO | Continuous | 7 | 6 | 5 | VERIFIED | Property lookup with owner data. Useful for pre-foreclosure skip-tracing. Not a direct foreclosure listing source. |
| Texas General Land Office / Texas.gov Notice Search | texasloanstar.net | Public Notice Website | NO | NO | NO | NO | NO | Monthly | 3 | 4 | 4 | UNVERIFIED | Aggregated state resource. Limited direct foreclosure data. Cross-reference only. |
| Foreclosure.com – Harris County | foreclosure.com | Foreclosure Platform | YES | YES | YES | NO | YES | Daily | 7 | 8 | 7 | VERIFIED | Aggregates public notice data. Addresses and estimated values shown. Subscription required for full access. |
| RealtyTrac – Harris County TX | realtytrac.com | Foreclosure Platform | YES | YES | YES | NO | YES | Daily | 6 | 7 | 7 | VERIFIED | Aggregates NOD and trustee-sale notices. Subscription required. Good for investor tracking. |
| PropertyRadar – Texas | propertyradar.com | Foreclosure Platform | YES | YES | YES | NO | YES | Daily | 9 | 9 | 9 | VERIFIED | Best-in-class trustee-sale monitoring. API available. Shows unpaid balances, trustee info, dates. |
| ATTOM Data – Texas Foreclosure Feed | attomdata.com | Foreclosure Platform | YES | YES | YES | YES | YES | Daily | 9 | 9 | 10 | VERIFIED | Institutional-grade. Full trustee-sale feeds via API. Used by hedge funds and institutional buyers. |
| BiggerPockets Foreclosure Listings – Houston | biggerpockets.com | Foreclosure Platform | YES | NO | NO | NO | YES | Weekly | 4 | 5 | 4 | UNVERIFIED | Community-driven aggregator. Less real-time. Good for market research only. |
| Buczek Enterprises – Trustee Sale Postings | buczekenterprises.com | Trustee Law Firm | YES | YES | YES | YES | YES | Monthly | 8 | 9 | 8 | VERIFIED | Major Texas substitute trustee firm. PDFs downloadable. Active in Harris, Dallas, Tarrant. |
| Barrett Daffin Frappier Turner & Engel LLP (BDF Group) | bdfgroup.com | Trustee Law Firm | YES | YES | YES | YES | YES | Monthly (~20 days prior) | 8 | 9 | 9 | VERIFIED | One of the largest Texas foreclosure trustee law firms. Thousands of Harris/Dallas/Tarrant sales. Searchable by county. |
| Mackie Wolf Zientz & Mann PC | mwzmlaw.com | Trustee Law Firm | YES | YES | YES | YES | YES | Monthly | 8 | 9 | 8 | VERIFIED | Major Texas trustee law firm. Extensive Harris County postings. PDFs available. Searchable listings. |
| Shapiro Schwartz LLP / LOGS.org | logs.org | Trustee Law Firm | YES | YES | YES | YES | YES | Monthly | 7 | 8 | 8 | VERIFIED | Texas-focused firm using LOGS.org for statewide notice posting. Legal newspaper integration. |
| Harris Courthouse Steps | (none — physical location) | Official County Source | YES | YES | NO | NO | YES | Monthly (first Tuesday) | 2 | 9 | 7 | VERIFIED | Physical auction at 201 Caroline St Houston TX. No online listing. Must attend or have local contact. |
| HAR.com – Foreclosure Integration | har.com | Public Notice Website | YES | NO | NO | NO | YES | Weekly | 5 | 6 | 5 | VERIFIED | Houston Association of Realtors MLS-adjacent data. Limited trustee-sale specifics. |
| Bid4Assets – Texas Tax Sales | bid4assets.com | Tax Sale Source | YES | NO | YES | NO | YES | Per-sale cycle | 8 | 7 | 7 | VERIFIED | Online tax deed auction platform. Harris County tax sales listed. Opening bids shown. |
| GovEase – Harris County Tax Sales | govease.com | Tax Sale Source | YES | NO | YES | NO | YES | Per-sale cycle | 8 | 7 | 7 | UNVERIFIED | Online government auction platform. Verify Harris County participation directly. |
| Texas Comptroller – Local Property Tax Sales | comptroller.texas.gov | Official County Source | NO | NO | NO | NO | NO | Annual | 3 | 5 | 4 | VERIFIED | State-level property tax resource. Links to county appraisal districts and tax offices. Not a direct listing source. |

---

### Dallas County TX (Dallas Metro)

| Field | Detail |
|-------|--------|
| **County** | Dallas County TX |
| **Market** | Dallas |
| **Auction Location** | George Allen Courts Building, 600 Commerce St, Dallas, TX 75202 |
| **First Tuesday Sale** | Monthly |

#### Dallas County Sources

| Trustee/Source Name | Website | Source Type | Addresses Shown | Owner Names | Opening Bids | PDFs Downloadable | Auction Dates Public | Update Frequency | Automation Score | Lead Quality Score | Investor Intel Score | Verification Status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Dallas County Clerk – Deed of Trust Foreclosure Notices | dallascounty.org | Official County Source | YES | YES | YES | YES | YES | Monthly | 7 | 9 | 9 | VERIFIED | Official Dallas County foreclosure notice repository. PDFs downloadable. Critical primary source. |
| Dallas Central Appraisal District (DCAD) | dallascad.org | Official County Source | YES | YES | NO | NO | NO | Continuous | 6 | 5 | 5 | VERIFIED | Property lookup for owner and value data. Useful for skip-tracing and pre-foreclosure research. |
| Barrett Daffin Frappier Turner & Engel LLP – Dallas | bdfgroup.com | Trustee Law Firm | YES | YES | YES | YES | YES | Monthly | 8 | 9 | 9 | VERIFIED | Dominant trustee firm in Dallas County. PDFs downloadable. Searchable by county. Must-have source. |
| Mackie Wolf Zientz & Mann PC – Dallas | mwzmlaw.com | Trustee Law Firm | YES | YES | YES | YES | YES | Monthly | 8 | 9 | 8 | VERIFIED | Active in Dallas County. Multi-county coverage. |
| Buczek Enterprises – Dallas Postings | buczekenterprises.com | Trustee Law Firm | YES | YES | YES | YES | YES | Monthly | 8 | 9 | 8 | VERIFIED | Multi-county Texas trustee firm. Dallas County postings included. |
| Foreclosure.com – Dallas TX | foreclosure.com | Foreclosure Platform | YES | YES | YES | NO | YES | Daily | 7 | 8 | 7 | VERIFIED | Aggregated Dallas County listings. Subscription for full data. |
| PropertyRadar – Dallas County | propertyradar.com | Foreclosure Platform | YES | YES | YES | YES | YES | Daily | 9 | 9 | 9 | VERIFIED | Excellent for Dallas County trustee-sale monitoring. Best automation candidate. |
| Dallas Morning News – Public Notices | dallasnews.com | Legal Newspaper | YES | YES | NO | NO | YES | Weekly | 5 | 7 | 5 | VERIFIED | State-required legal newspaper for Dallas County. Trustee sale notices published. Searchable online. |
| Dallas County Tax Office – Delinquent Tax Sales | dallascountytax.com | Tax Sale Source | YES | NO | YES | NO | YES | Per-sale cycle | 6 | 7 | 6 | VERIFIED | Dallas County tax sale listings. Delinquent property tax auctions. |
| Dallas Courthouse Steps – George Allen Courthouse | (none — physical location) | Official County Source | YES | YES | NO | NO | YES | Monthly (first Tuesday) | 2 | 9 | 7 | VERIFIED | Physical auction at 600 Commerce St Dallas TX. No online live feed. |
| Texas HOA Foreclosure Filings – Dallas | dallascounty.org | HOA Foreclosure Source | YES | YES | NO | YES | YES | Monthly | 6 | 7 | 5 | UNVERIFIED | HOA foreclosure notices filed with Dallas County Clerk. Cross-reference with deed of trust filings. |
| LOGS.org – Legal Notice Platform Texas | logs.org | Public Notice Website | YES | YES | YES | YES | YES | Monthly | 7 | 8 | 7 | VERIFIED | Statewide Texas legal notice aggregator used by multiple trustee firms. Searchable by county. |

---

### Tarrant County TX (Fort Worth / Arlington Metro)

| Field | Detail |
|-------|--------|
| **County** | Tarrant County TX |
| **Market** | Fort Worth / Arlington |
| **Auction Location** | Tim Curry Criminal Justice Center, 200 Taylor St, Fort Worth, TX 76196 |
| **First Tuesday Sale** | Monthly |

#### Tarrant County Sources

| Trustee/Source Name | Website | Source Type | Addresses Shown | Owner Names | Opening Bids | PDFs Downloadable | Auction Dates Public | Update Frequency | Automation Score | Lead Quality Score | Investor Intel Score | Verification Status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Tarrant County Clerk – Foreclosure Notices | tarrantcounty.com | Official County Source | YES | YES | YES | YES | YES | Monthly | 7 | 9 | 9 | VERIFIED | Official Tarrant County foreclosure filing repository. Critical primary source. Covers Fort Worth and Arlington. |
| Tarrant Appraisal District (TAD) | tad.org | Official County Source | YES | YES | NO | NO | NO | Continuous | 6 | 5 | 5 | VERIFIED | Property lookup for Tarrant County. Owner and valuation data. Useful for skip-tracing. |
| Barrett Daffin Frappier Turner & Engel LLP – Tarrant | bdfgroup.com | Trustee Law Firm | YES | YES | YES | YES | YES | Monthly | 8 | 9 | 9 | VERIFIED | Dominant trustee firm in Tarrant County. Same platform as Harris/Dallas entries. |
| Mackie Wolf Zientz & Mann PC – Tarrant | mwzmlaw.com | Trustee Law Firm | YES | YES | YES | YES | YES | Monthly | 8 | 9 | 8 | VERIFIED | Active in Tarrant County. Multi-county Texas coverage. |
| Buczek Enterprises – Tarrant Postings | buczekenterprises.com | Trustee Law Firm | YES | YES | YES | YES | YES | Monthly | 8 | 9 | 8 | VERIFIED | Multi-county Texas trustee firm. Tarrant County coverage. |
| Foreclosure.com – Fort Worth TX | foreclosure.com | Foreclosure Platform | YES | YES | YES | NO | YES | Daily | 7 | 8 | 7 | VERIFIED | Aggregated Tarrant County listings. Fort Worth and Arlington coverage. Subscription required. |
| PropertyRadar – Tarrant County | propertyradar.com | Foreclosure Platform | YES | YES | YES | YES | YES | Daily | 9 | 9 | 9 | VERIFIED | Best automation candidate for Tarrant County. Multi-county coverage on same platform. |
| Fort Worth Star-Telegram – Public Notices | star-telegram.com | Legal Newspaper | YES | YES | NO | NO | YES | Weekly | 5 | 7 | 5 | VERIFIED | State-required legal newspaper for Tarrant County. Trustee sale notices published per Texas law. |
| Tarrant County Tax Office – Tax Delinquent Sales | tarrantcounty.com | Tax Sale Source | YES | NO | YES | NO | YES | Per-sale cycle | 6 | 7 | 6 | VERIFIED | Tarrant County tax delinquent property auctions. Opening bids reflect tax lien amounts. |
| Tarrant Courthouse Steps – Tim Curry Justice Center | (none — physical location) | Official County Source | YES | YES | NO | NO | YES | Monthly (first Tuesday) | 2 | 9 | 7 | VERIFIED | Physical auction at 200 Taylor St Fort Worth TX. No online live feed. |
| LOGS.org – Tarrant County Notices | logs.org | Public Notice Website | YES | YES | YES | YES | YES | Monthly | 7 | 8 | 7 | VERIFIED | Covers Tarrant County trustee-sale notices. Multi-county PDF download capability. |
| Arlington Morning News – Public Notices | arlingtonmorningnews.com | Legal Newspaper | YES | YES | NO | NO | YES | Weekly | 4 | 6 | 4 | UNVERIFIED | Arlington-area legal newspaper. Trustee-sale notices for Tarrant County Arlington market. Cross-reference source. |

---

## Score Legend

| Score Range | Automation Score Meaning | Lead Quality Meaning | Investor Intel Meaning |
|---|---|---|---|
| 9-10 | Highly automatable — API or clean HTTP/PDF | Excellent lead data — address + owner + bid | Institutional-grade data for fund analysis |
| 7-8 | Good automation potential — PDF parse or Playwright | Strong lead data with most key fields | Good for tracking institutional buyer patterns |
| 5-6 | Moderate — some manual steps required | Decent data, missing one or two key fields | Some market intelligence value |
| 3-4 | Low — mostly manual or partial data | Limited data, mostly research-level | Limited investment intelligence |
| 1-2 | Effectively manual only | Must attend in person | Primarily qualitative intelligence |

---

## Verification Status Key

- **VERIFIED** — Source confirmed to exist and contain described data as of 2026-05-16
- **UNVERIFIED** — Source listed but not confirmed active or URL not validated; requires manual check

---

*Last Updated: 2026-05-16 | AMARA-AI Texas Foreclosure Intel Module*
