# Source Log — Clark County NV Tax Delinquent OSINT
Generated: 2026-05-18  
Workflow: AMARA OS Tax Delinquent OSINT Builder

---

## SOURCE 1 — 2021 Clark County Trustee Auction Notice
**Document:** `758aced6-SF_DD_2cbd23ac3d9c405b8f46f0e7187b4d06.pdf`  
**Document Type:** Official Clark County Treasurer Notice of Trustee Auction  
**Auction Dates:** May 13–14, 2021 (online via Bid4Assets.com/ClarkNV)  
**Deadline to Redeem:** 5:30 PM Monday, May 10, 2021  
**Issuing Office:** Clark County Treasurer, Laura B. Fitzpatrick, Treasurer  
**Address:** 500 S. Grand Central Pkwy, 1st Floor, P.O. Box 551220, Las Vegas, NV 89155  
**Phone:** (702) 455-3072  
**Published In:** Las Vegas Review-Journal, April 21, 25 & May 5, 9, 2021  
**Extraction Method:** PDF OCR via Tesseract (poppler pdfimages + tesseract-ocr 5.3.4)  

**Fields extracted from this source:**
- APN (Parcel Number)
- Minimum Bid Amount (includes taxes, penalties, interest, costs as of notice date)
- Owner Name (from assessor record at time of publication)
- Assessor Legal Description
- Property Location (situs address or UNASSIGNED SITUS)

**Notes:**
- Parcel data was in scanned image format (JPEG embedded in PDF), requiring OCR
- OCR introduced some errors in APN formatting (spaces within APN digits) — normalized in processing
- Owner names on multi-line entries (continuation on prior line) were manually reconciled
- `#` flag = manufactured/personal property NOT included in real property sale (land only)
- `**` flag = parcel group sold as one auction item (4 parcels: 243-35-311-010, -011, -016, -017)
- Minimum bid amounts represent taxes + penalties + interest + costs as of April 2021
- All properties sold AS IS with possible remaining liens per auction notice
- **75 unique APNs extracted; approximately 71 auction items** (4 APNs in one group sale)

**Primary Source URL:**  
https://www.clarkcountynv.gov/government/departments/treasurer/real_property_tax_auction.php

---

## SOURCE 2 — 2024 Clark County Annual Delinquency Publication
**Document:** `fbb6aa5e-annualdelinquencypublication05152024.pdf`  
**Document Type:** Official Clark County Treasurer Notice of Delinquent Taxes — FY2023-2024  
**Coverage Period:** July 1, 2023 – June 30, 2024  
**Delinquency As Of:** May 1, 2024  
**Certificate Issuance Deadline:** June 3, 2024 (first Monday in June)  
**Redemption Period:** 2 years from certificate date (per NRS 361); abandoned properties 1 year  
**Interest Rate on Delinquency:** 10% annual rate, assessed monthly (per NRS 361)  
**Issuing Office:** Clark County Treasurer, J. Ken Diaz, Treasurer  
**Published In Accordance With:** Nevada Revised Statutes (NRS) 361.565  
**Extraction Method:** pdftotext with `-layout` flag; Python regex parser  

**Fields extracted from this source:**
- APN (Parcel Number)
- Owner Name (from assessor record as of publication)
- Taxes (base tax amount delinquent)
- Penalties/Interest (accumulated pen/int as of May 1, 2024)
- Cost (administrative costs)
- Total Owed (calculated sum)

**Fields NOT available in this source (require external lookup):**
- Property address (need Clark County Assessor)
- Mailing address (need Clark County Assessor)
- Assessed value (need Clark County Assessor)
- Property type/characteristics (need Assessor)
- Deed/lien history (need Clark County Recorder)
- LLC/entity status (need Nevada Secretary of State)
- Court/probate status (need Clark County District Court)

**Records Extracted:** 8,660 unique parcels  
**Multi-parcel owners identified:** 609 owners with 2+ delinquent parcels  

**Primary Source URL:**  
https://www.clarkcountynv.gov/government/departments/treasurer/delinquent_taxes.php

---

## SOURCE 3 — CROSS-REFERENCE ANALYSIS (Internal)
**Method:** Python set intersection of APN values from Source 1 and Source 2  
**Finding:** 15 APNs appear in BOTH the 2021 auction list AND the 2024 delinquency list  
**Significance:** These parcels have been in continuous or recurring tax delinquency for 3+ years  

**Cross-Referenced Parcels:**

| APN | 2021 Auction Owner | 2024 Owner | 2024 Owed | Change? |
|-----|--------------------|------------|-----------|---------|
| 030-25-501-013 | LEAVITT LEROY J | LEAVITT LEROY J | $4,074.26 | Same owner |
| 030-25-501-014 | LEAVITT LEROY J | LEAVITT LEROY J | $4,060.26 | Same owner |
| 040-13-301-018 | HESSE ROBERT A | HESSE ROBERT A | $1,283.64 | Same owner |
| 040-23-801-011 | HESSE ROBERT A | HESSE ROBERT A | $1,997.80 | Same owner |
| 070-13-211-034 | JEPPSON MAY OR ARNOLD | BJT HOLDINGS LLC | $157.26 | OWNER CHANGED — sold at 2021 auction, new owner now delinquent |
| 138-03-513-034 | STEWART SABINE FAMILY TRUST | STEWART SABINE FAMILY TRUST | $2,243.27 | Same owner |
| 139-15-210-240 | WENZEL FAMILY LIVING TRUST | WENZEL JACK L | $60.70 | Name variant — likely same family |
| 139-16-310-029 | DOMENICK RONALD A / MARTINEZ RUTH M | MUHAMMAD MONNIKA | $140.37 | OWNER CHANGED — possibly sold/transferred |
| 139-16-610-334 | BEREAN CHRISTIAN FELLOWSHIP | BEREAN CHRISTIAN FELLOWSHIP | $137.35 | Same owner |
| 161-17-616-068 | SONDEJ KENNETH | SANCHEZ ANDRES MANDUJANO | $159.70 | OWNER CHANGED — transferred |
| 179-16-114-052 | BLOOM DAVID S & JUDITH M | BLOOM DAVID S & JUDITH M | $10,826.70 | Same owner — still delinquent after 3 years |
| 243-35-311-010 | BRADLEY DONALD E & CAROLYN M | BRADLEY DONALD E & CAROLYN M | $7,471.06 | Same owner |
| 243-35-311-011 | BRADLEY DONALD E & CAROLYN M | WILLIAMS MIKE | $602.13 | Name variant — group sale |
| 243-35-311-016 | BRADLEY DONALD E & CAROLYN M | WILLIAMS MIKE | $1,339.97 | Name variant — group sale |
| 243-35-311-017 | BRADLEY DONALD E & CAROLYN M | WILLIAMS MIKE | $206.81 | Name variant — group sale |

---

## SOURCES NOT YET QUERIED (Manual Action Required)

The following sources were identified as required but could NOT be automatically queried
(access requires human browser interaction, login, or real-time scraping):

### A. Clark County Assessor
- **URL:** https://assessor.clarkcountynv.gov/assrapp/assessment/SitePages/showDetail.aspx
- **Use For:** Property address, assessed value, owner mailing address, property type, lot size, year built
- **Access Method:** Public web search by APN or address (no login required)
- **Priority APNs:** All 75 auction APNs + top 50 from 2024 delinquency list

### B. Clark County Recorder
- **URL:** https://recorder.clarkcountynv.gov/forsearch/search
- **Use For:** Deed history, liens, notices of default, HOA liens, IRS liens, quitclaim deeds, trustee deeds
- **Access Method:** Public search by APN (no login required)
- **Priority:** All STRONG TARGET and HOT TARGET APNs

### C. Clark County Eighth Judicial District Court
- **URL:** https://www.clarkcountycourts.us/Anonymous/default.aspx
- **Use For:** Civil cases, foreclosures, judgments, divorce filings, probate cases
- **Search By:** Owner name
- **Priority:** Estate owners, ETAL owners, trust owners

### D. Clark County Probate / Surrogate Records
- **URL:** https://www.clarkcountycourts.us/Anonymous/default.aspx (same portal — select Probate)
- **Use For:** Probate case numbers, estate filings, heir identification
- **Priority:** BADALI JOSEPHINE ESTATE (APN 139-15-210-256) — IMMEDIATE

### E. Nevada Secretary of State Business Search
- **URL:** https://esos.nv.gov/EntitySearch/OnlineEntitySearch
- **Use For:** LLC/corp registration status, active/revoked/dissolved, registered agent, formation date
- **Priority LLC owners to check:**
  - REAL ESTATE DEVELOPMENT LLC (APN 138-01-406-008)
  - BMR FUNDING LLC (APNs 140-17-401-001, 140-17-401-002)
  - REALTY DATA GROUP LLC (APNs 139-21-210-007, 140-29-101-016)
  - MARQUES INVESTMENTS LLC (APN 140-30-215-008)
  - MILLER VISTA LAS VEGAS 276 LLC (APNs 139-16-310-321 through 324)
  - CORNERSTONE HOLDINGS LLC (APN 139-35-713-029)
  - SMITH & PARKER LLC (APN 162-11-213-006)
  - STRAWBERRY FIELD LLC (APN 140-15-411-041)
  - C & C LAS VEGAS LLC (55 parcels in 2024 list)
  - SKY RANCH HOLDINGS LLC (16 parcels in 2024 list)
  - BOX REVOCABLE LIVING TRUST (16 parcels — check grantor status)

### F. Google/Bing Obituary Search
- **Method:** Search: "[owner name]" obituary Nevada Las Vegas
- **Priority:** BADALI JOSEPHINE ESTATE, WENZEL FAMILY LIVING TRUST, SHEBAH TRUST owners
- **Also check:** "EPSTEIN KENNETH" obituary (APN 138-18-710-121, $294,845.94 auction)

### G. Google Maps / Street View
- **Method:** Manual URL: https://www.google.com/maps/search/[address]+Las+Vegas+NV
- **Priority:** All "UNASSIGNED SITUS" parcels — verify vacant land vs. addressed property

### H. Clark County Treasurer Real-Time Tax Inquiry
- **URL:** https://treasurer.clarkcountynv.gov/treasurer-home/real-property-tax-inquiry
- **Use For:** CURRENT tax status — some 2021 auction parcels may have been redeemed or sold
- **IMPORTANT:** 2021 auction data is 3+ years old — verify current status before outreach

---

## DATA INTEGRITY NOTES

1. **2021 Auction Data Currency:** This auction was held in May 2021. The parcels listed may have been:
   - Sold at auction (new owner — verify at Assessor)
   - Redeemed by original owner before auction
   - Still held by Clark County Trustee
   - The cross-reference with 2024 data provides some evidence of current status

2. **OCR Accuracy:** APN numbers from the scanned 2021 auction PDF were OCR-extracted. 
   Verification of each APN against the Clark County Assessor database is required.
   Known OCR artifacts corrected: spaces in APN mid-number (e.g., "123-30-51 1-074" → "123-30-511-074")

3. **Years Delinquent Estimation:** For 2024 delinquency parcels, years delinquent was estimated 
   by penalty/interest-to-base-tax ratio (10% annual per NRS 361). This is an approximation only.

4. **No Data Invented:** All data in the output files comes directly from:
   - The two uploaded PDF documents
   - Mathematical calculations on that data
   - Cross-reference analysis between the two documents
   - Source URLs pointing to public Clark County portals for verification
   - Fields marked "UNVERIFIED" contain no fabricated data

5. **Bankruptcy Notice:** Per the 2024 delinquency publication: "IF YOU HAVE FILED FOR BANKRUPTCY 
   RELIEF, THIS NOTICE MAY NOT APPLY TO YOU." Bankruptcy status of any owner is unknown without 
   court records check.
