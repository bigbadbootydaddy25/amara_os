# Execution Report — Clark County NV Tax Delinquent OSINT
**Generated:** 2026-05-18  
**Workflow:** AMARA OS Tax Delinquent OSINT Builder  
**Status:** Phase 1 Complete — Document Extraction & Scoring  
**Phase 2:** Manual OSINT Verification Required (see manual_review_queue.csv)

---

## SUMMARY OF FINDINGS

### Dataset 1 — 2021 Clark County Trustee Auction
- **Source:** Clark County Treasurer Notice of Trustee Auction, May 13-14, 2021
- **APNs Extracted:** 75 unique APNs (75 parcels; ~71 auction sale items; 4 in one group)
- **Total Minimum Bid Value:** $2,581,199 across all auction parcels
- **Key Signal:** These parcels were already delinquent enough for county trustee sale — 3+ years minimum delinquency

### Dataset 2 — 2024 Annual Delinquency Publication (FY2023-2024)
- **Source:** Clark County Treasurer Annual Delinquency Notice, published May 15, 2024
- **APNs Extracted:** 8,660 unique parcels
- **Multi-Parcel Delinquent Owners:** 609 owners with 2+ delinquent parcels
- **Single largest delinquent entity:** C & C LAS VEGAS LLC — 55 delinquent parcels

### Cross-Reference
- **15 APNs** appear in BOTH the 2021 auction list AND 2024 delinquency list
- **7 of those 15** have the SAME owner in both years — these are extreme distress cases
- **3 of those 15** show OWNERSHIP CHANGES — the 2021 auction property transferred to a new owner who is ALSO now delinquent

---

## TOP 10 HOT TARGETS (from 2021 Auction List)
*Note: No parcels scored 80+ using only document data. Scores will increase significantly once 
assessor/recorder/court data is verified. These are the top 7 STRONG TARGETS.*

### Rank 1 — BADALI JOSEPHINE ESTATE
- **APN:** 139-15-210-256
- **Score:** 70 (STRONG TARGET — will likely upgrade to HOT after probate verification)
- **Owner:** BADALI JOSEPHINE ESTATE
- **Address:** UNASSIGNED SITUS (vacant lot, East Las Vegas area)
- **Min Bid 2021:** $1,479.89
- **Why It's Hot:** ESTATE in owner name = deceased owner signal. Unassigned situs = vacant land. 3+ years delinquent. This is a prime probate acquisition target. File a probate search immediately.
- **Action:** Search Clark County Probate: https://www.clarkcountycourts.us — search "BADALI JOSEPHINE"
- **Source:** 2021 Trustee Auction, Page 1

### Rank 2 — REAL ESTATE DEVELOPMENT LLC
- **APN:** 138-01-406-008
- **Score:** 65 (STRONG TARGET)
- **Owner:** REAL ESTATE DEVELOPMENT LLC
- **Address:** 5472 W ALEXANDER RD, Las Vegas NV (commercial/industrial area)
- **Min Bid 2021:** $131,570.92
- **Why It's Hot:** Large LLC with $131K+ in delinquent taxes. LLC likely revoked/dissolved after years of non-payment. Significant commercial property in NW Las Vegas. High dollar value with potentially distressed entity.
- **Action:** 1) NV SOS entity search for "REAL ESTATE DEVELOPMENT LLC"; 2) Clark County Assessor for property type/value; 3) Recorder for deed/lien history
- **Source:** 2021 Trustee Auction, Page 1

### Rank 3 — BMR FUNDING LLC ETAL (UNASSIGNED SITUS)
- **APN:** 140-17-401-002
- **Score:** 60 (STRONG TARGET)
- **Owner:** BMR FUNDING LLC ETAL
- **Address:** UNASSIGNED SITUS (partner to 140-17-401-001 at 2550 N Lamb Blvd)
- **Min Bid 2021:** $49,520.75
- **Why It's Hot:** LLC entity + unassigned situs (likely vacant land adjacent to 2550 N Lamb). $49K minimum bid. Multi-parcel (also owns 140-17-401-001).
- **Action:** NV SOS for BMR FUNDING LLC; Assessor for both parcels 140-17-401-001 and -002
- **Source:** 2021 Trustee Auction, Page 2

### Rank 4 & 5 — LEAVITT LEROY J (2 parcels)
- **APNs:** 030-25-501-013, 030-25-501-014
- **Score:** 60 each (STRONG TARGET)
- **Owner:** LEAVITT LEROY J
- **Address:** UNASSIGNED SITUS (both — remote land, likely Clark County outskirts)
- **Min Bid 2021:** $3,087 and $3,073
- **Why They're Hot:** SAME OWNER STILL DELINQUENT IN 2024 ($4,074 and $4,060 respectively still owed). This means 5+ years of continuous delinquency. Owner either abandoned these parcels or cannot pay. Extreme distress signal. Also note: LEAVITT FAMILY TRUST (APN 071-30-101-009) also appears in auction — same family, 3+ delinquent parcels.
- **Action:** Search Clark County Assessor + obituary/probate check for Leroy J. Leavitt
- **Source:** Both 2021 auction AND 2024 delinquency publication (CROSS-REFERENCED)

### Rank 6 & 7 — HESSE ROBERT A (2 parcels)
- **APNs:** 040-13-301-018, 040-23-801-011
- **Score:** 60 each (STRONG TARGET)
- **Owner:** HESSE ROBERT A
- **Address:** UNASSIGNED SITUS (both — remote rural parcels, SEC 13 and SEC 23)
- **Min Bid 2021:** $1,193 and $1,679
- **Why They're Hot:** SAME OWNER STILL DELINQUENT IN 2024. Individual owner with abandoned rural land. 5+ years continuous delinquency. Low minimum bid makes entry barrier very low.
- **Action:** Obituary/skip trace on Robert A. Hesse; assessor lookup for acreage/zoning
- **Source:** Both 2021 auction AND 2024 delinquency (CROSS-REFERENCED)

---

## TOP DECEASED/PROBATE CANDIDATES

### 1. BADALI JOSEPHINE ESTATE — APN 139-15-210-256 (PRIORITY #1)
Estate flagged in owner name. Immediate probate search required.

### 2. WENZEL FAMILY LIVING TRUST — APN 139-15-210-240
Still delinquent in 2024 (under "WENZEL JACK L"). Trust grantor status unknown — may be deceased.  
Check Clark County Probate for WENZEL, JACK L and related trusts.

### 3. SHEBAH TRUST / SHEBAH YHIEL TRS — APNs 139-27-811-015 AND 139-27-811-016
Two parcels in one trust ($121K + $107K auction). High-value trust with massive tax delinquency.  
715 Bell Dr and 721 Bell Dr, Las Vegas. Verify trustee/grantor status immediately.

### 4. AGUSTIN DANNY JOE PROPERTY TRUST — APN 139-35-610-042
Trust + individual name (Garcia Dany TRS). $166,919 minimum bid. 1805 Poplar Ave, Las Vegas.  
High-value probate/trust acquisition target. Property trust with potential heir dispute.

### 5. LEAVITT FAMILY TRUST — APN 071-30-101-009
Trust + 2 individual Leavitt parcels also delinquent. Family trust with manufactured home excluded  
from sale. Searchlight NV area. Check if Leavitt family has any probate case.

### 6. STEWART SABINE FAMILY TRUST — APN 138-03-513-034
Appears in BOTH 2021 auction AND 2024 delinquency ($2,243 still owed in 2024). Trust still  
delinquent 3+ years later. 7013 Old Village Ave, Las Vegas. High priority probate check.

### BOX REVOCABLE LIVING TRUST (2024 list)
16 parcels delinquent in 2024 under this trust. Likely deceased grantor. Immediate skip trace.

### OHANIAN KARLO TRUST (2024 list)  
12 parcels delinquent. Trust with possible deceased owner. High portfolio value.

---

## TOP LLC/ENTITY DISTRESS CANDIDATES

### From 2021 Auction List:
1. **REAL ESTATE DEVELOPMENT LLC** — APN 138-01-406-008 — $131,570.92 — 5472 W Alexander Rd
2. **REALTY DATA GROUP LLC** — APNs 140-29-101-016 ($93,953) + 139-21-210-007 ($41,122) — Multi-parcel
3. **MARQUES INVESTMENTS LLC** — APN 140-30-215-008 — $92,505.80 — 3601 Valley Forge Ave
4. **BMR FUNDING LLC** — APNs 140-17-401-001 + -002 — $99,265 combined
5. **MILLER VISTA LAS VEGAS 276 LLC** — 4 parcels (Vista St addresses) — $6,982 total
6. **CORNERSTONE HOLDINGS LLC** — APN 139-35-713-029 — $45,717 — 2120 Ash Ave
7. **STRAWBERRY FIELD LLC** — APN 140-15-411-041 — $21,253 — 2558 Athena Dr

### From 2024 Delinquency List (Top Multi-Parcel LLCs):
1. **C & C LAS VEGAS LLC** — 55 parcels delinquent — LARGEST PORTFOLIO (check NV SOS immediately)
2. **SKY RANCH HOLDINGS LLC** — 16 parcels delinquent
3. **VR INVESTMENTS LLC** — 13 parcels delinquent
4. **NEO VEGAS LLC** — 12 parcels delinquent
5. **LV PROPERTY HOLDINGS ONE LLC** — 11 parcels delinquent
6. **NEVADA INVESTMENTS & TRADE MGM** — 11 parcels delinquent
7. **BJT HOLDINGS LLC** — 9 parcels — NOTE: Acquired 070-13-211-034 from 2021 auction, NOW delinquent again

---

## TITLE RED FLAGS

### High Complexity Titles:
1. **STROBEHN RISEL ETAL** — APN 030-25-501-015 — $39,961 — Multiple owners (ETAL)
2. **JACK CHARLES E IV & TRACY J ETAL** — APN 126-02-201-003 — Multiple owners
3. **WEIS SOLVEIG ETAL** — APN 161-17-511-109 — $35,701 — 3344 Vista Del Monte Dr
4. **BABERO ANDRAS F & HARRIET K / BABERO BERT B JR** — APN 139-22-711-094 — 3 named owners
5. **RAZON LORE ETAL** — APN 139-15-210-425 — Multiple owners on vacant lot
6. **COLLINS BILL ETAL** — APN 139-16-610-009 — Vacant lot, multiple owners

### Group Sale (Title Complexity):
- **243-35-311-010/011/016/017** — BRADLEY DONALD E & CAROLYN M WILLIAMS / MIKE — 4 parcels, 3 named owners, sold as ONE group in 2021 auction. Still delinquent in 2024 under WILLIAMS MIKE. Complex multi-owner chain.

### Ownership Transfers (2021→2024):
- **070-13-211-034:** JEPPSON → BJT HOLDINGS LLC (post-auction transfer, BJT now delinquent again)
- **139-16-310-029:** DOMENICK/MARTINEZ → MUHAMMAD MONNIKA (transferred, still delinquent)
- **161-17-616-068:** SONDEJ → SANCHEZ ANDRES (transferred, still delinquent)

---

## RECOMMENDED FIRST OUTREACH LIST

Priority order based on motivation score + deal potential + data confidence:

| Priority | APN | Owner | Address | Score | Why Outreach Now |
|----------|-----|-------|---------|-------|-----------------|
| 1 | 139-15-210-256 | BADALI JOSEPHINE ESTATE | UNASSIGNED SITUS | 70 | Estate/probate — heir contact before county takes |
| 2 | 138-01-406-008 | REAL ESTATE DEVELOPMENT LLC | 5472 W ALEXANDER RD | 65 | LLC likely revoked, $131K+ delinquency |
| 3 | 179-16-114-052 | BLOOM DAVID S & JUDITH M | 120 KAVA KAVA ST, Henderson | 55 | Same owners still delinquent in 2024 ($10,826 additional) — open to deal |
| 4 | 139-27-811-015 | SHEBAH YHIEL TRS | 715 BELL DR | 50 | Trust, $121K bid, dual parcels (715 + 721 Bell) |
| 5 | 139-27-811-016 | SHEBAH YHIEL TRS | 721 BELL DR | 50 | Same trust, $107K bid — buy both as package |
| 6 | 030-25-501-013 | LEAVITT LEROY J | UNASSIGNED SITUS | 60 | Still delinquent in 2024 — abandoned land |
| 7 | 030-25-501-014 | LEAVITT LEROY J | UNASSIGNED SITUS | 60 | Same — 2 parcel package opportunity |
| 8 | 040-13-301-018 | HESSE ROBERT A | UNASSIGNED SITUS | 60 | Still delinquent in 2024 — rural land |
| 9 | 140-29-101-016 | REALTY DATA GROUP LLC | 4550 E VAN BUREN AVE | 45 | $93K LLC, multi-parcel — entity distress |
| 10 | 140-30-215-008 | MARQUES INVESTMENTS LLC | 3601 VALLEY FORGE AVE | 45 | $92K LLC — entity distress |

---

## PARCELS NEEDING MANUAL REVIEW

All 40 parcels in `manual_review_queue.csv` require manual OSINT before outreach.

**Most critical manual reviews:**
1. All APNs with "UNASSIGNED SITUS" — verify vacant lot vs. unaddressed improved property at Assessor
2. All LLC/entity owners — run NV SOS entity search to confirm revoked/active status
3. All trust owners — run Clark County Probate search to identify deceased grantors
4. Cross-referenced parcels — run current tax status check at Treasurer portal
5. APNs 139-27-811-015 and -016 (SHEBAH) — high dollar value, verify current ownership chain

---

## IMPORTANT DISCLAIMERS

1. **Data Currency:** 2021 auction data is approximately 3+ years old. All property ownership, tax
   status, and auction outcomes MUST be verified against current records before any outreach.
   
2. **Bankruptcy Warning:** Any owner may have filed bankruptcy. This OSINT does not include
   bankruptcy screening. Do not contact any party in known bankruptcy without legal counsel review.
   
3. **No Fabricated Data:** Every data point in these files comes directly from the two uploaded
   PDFs, mathematical derivations thereof, or is explicitly marked UNVERIFIED.
   
4. **Legal Compliance:** All outreach activities must comply with applicable laws including 
   the FDCPA, TCPA, CAN-SPAM, and Nevada real estate regulations.
   
5. **Robots.txt Compliance:** All suggested source URLs are publicly accessible government portals.
   No credentials or login bypass was used or suggested.
