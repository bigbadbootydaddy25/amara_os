# TITLE RED FLAGS REGISTER
## Property: 1516 W 34TH ST #1 / UNIT 10, Houston TX 77018
## HCAD: 061-039-000-0020 | Cause #: 201812599
## Report Date: 2026-05-16

---

## 🔴 CRITICAL RED FLAGS (Deal-Stopping if Confirmed)

### RF-001 — UNCONFIRMED 2023 DEED TRANSFER
- **Risk Level:** 🔴 CRITICAL
- **Description:** Third-party real estate portals (Zillow, Redfin, Trulia) reference a property sale event at this address on approximately **March 9, 2023**. Texas is a non-disclosure state so the price is hidden. No new owner name is visible in any public data source.
- **Implication:** If a deed was recorded in 2023, NANGUNORRI RAMESHWARRAO may NO LONGER BE THE OWNER OF RECORD. Pursuing a tax sale acquisition or owner-approach deal based on an outdated record could result in dealing with the wrong party and potential fraud exposure.
- **Resolution Required:** Harris County Clerk RP records search MUST be run to determine whether a deed was recorded and who the current grantee is.

### RF-002 — ENTIRE CHAIN OF TITLE UNVERIFIED
- **Risk Level:** 🔴 CRITICAL
- **Description:** No deed documents, mortgage records, lien releases, or other recorded instruments were found or confirmed through automated OSINT. Harris County Clerk records are inaccessible via automated tools.
- **Implication:** Unknown encumbrances, multiple mortgages, IRS liens, abstracts of judgment, or other clouds could be attached to the title with no way to know from available data.
- **Resolution Required:** Full chain-of-title search by licensed title company.

### RF-003 — BANKRUPTCY STATUS UNVERIFIED
- **Risk Level:** 🔴 CRITICAL
- **Description:** PACER was not searchable. No bankruptcy filing was confirmed or ruled out. An active automatic stay would void any tax sale or property transfer.
- **Implication:** If owner has an active bankruptcy case, proceeding with any acquisition or assignment could violate federal law (11 U.S.C. § 362) and expose the acquirer to sanctions.
- **Resolution Required:** PACER search required before any money changes hands.

### RF-004 — IRS LIEN STATUS UNKNOWN
- **Risk Level:** 🔴 CRITICAL
- **Description:** IRS federal tax liens are recorded at the Harris County Clerk's office. No IRS lien search was possible via automated tools. IRS liens are NOT extinguished by a state tax sale unless the IRS received proper 25-day advance notice under IRC § 7425.
- **Implication:** A tax deed purchaser could take title subject to an existing IRS lien, which the IRS can enforce or use to redeem within 120 days of the sale.
- **Resolution Required:** Harris County Clerk federal tax lien search; verify whether taxing entities gave IRS proper notice; contact IRS Centralized Lien Processing at 800-913-6050.

---

## 🟠 MAJOR RED FLAGS (Significant Risk — Requires Investigation)

### RF-005 — 8 YEARS OF TAX DELINQUENCY
- **Risk Level:** 🟠 MAJOR
- **Description:** Tax delinquency runs from 2016 through 2023 — **8 consecutive years** on a property with an adjudged value of $877,917.
- **Implication:** An owner who allows 8 years of delinquency on a valuable multi-family property typically indicates one or more of: financial distress, active bankruptcy proceedings, title dispute preventing sale, property abandonment, estate/probate issues, or owner being unreachable (deceased or out of state). Each of these creates additional complications.
- **Resolution Required:** Owner background investigation; PACER search; probate search; review of full tax suit docket.

### RF-006 — ADJUDGED VALUE vs. MINIMUM BID GAP
- **Risk Level:** 🟠 MAJOR
- **Description:** Adjudged value is $877,917 but minimum bid is $192,085 — a gap of **$685,832**. This gap suggests substantial equity above the tax obligation.
- **Implication:** Properties with significant equity above the tax obligation attract more bidders at auction, making pre-auction acquisition more difficult. The large gap also suggests the property likely has outstanding mortgages or other liens that reduce the net equity. There may also be competing interests from heirs, tenants, or other parties who may try to redeem or challenge the sale.
- **Resolution Required:** Mortgage/lien search to determine true net equity.

### RF-007 — MULTI-FAMILY PROPERTY COMPLEXITY
- **Risk Level:** 🟠 MAJOR
- **Description:** The property is a B2 multi-family building (1950, multiple units including at least Unit 10). Multiple tenants may be occupying units under lease agreements.
- **Implication:** Texas Property Code tenant protections apply. A tax deed purchaser must provide proper notice to tenants. Occupied units may slow possession. Multi-family properties also carry higher code enforcement risk, habitability liability, and potential for city-filed liens.
- **Resolution Required:** Property visit to assess occupancy; review any lease agreements; confirm code compliance status with Houston Permitting Center.

### RF-008 — OWNER NAME INCONSISTENCY / SPELLING VARIATIONS
- **Risk Level:** 🟠 MAJOR
- **Description:** The owner name appears in multiple formats: NANGUNORRI RAMESHWARRAO (HCAD reversed), Nangunoori Rameshwar Rao, Rameshwar R Nangunoori, etc. Indian surnames are frequently transliterated inconsistently into county records.
- **Implication:** A chain-of-title search that misses a name variant could fail to find recorded deeds, liens, or judgments that were indexed under a different spelling. This is a known title gap for properties owned by individuals with non-Western names.
- **Resolution Required:** All 5+ name variants must be searched at every source; title company must be instructed to search all variants.

### RF-009 — OUT-OF-STATE OWNER / CONTACT ADDRESS
- **Risk Level:** 🟠 MAJOR
- **Description:** Skip trace indicates a possible contact address in Greer, South Carolina (344 Claybrooke Dr, Greer SC 29650). If the owner is actually located out of state, this affects owner outreach, service of process, and the feasibility of a pre-auction deal.
- **Implication:** Owner outreach for any pre-sale assignment or deed-in-lieu requires locating and serving the actual owner. Out-of-state owners are harder to reach and may require different legal approaches. Skip trace address is NOT verified as current residence.
- **Resolution Required:** Independent owner contact verification; confirm identity at SC address before any offer.

---

## 🟡 YELLOW FLAGS (Elevated Risk — Monitor / Investigate)

### RF-010 — HOA STATUS UNKNOWN
- **Risk Level:** 🟡 YELLOW
- **Description:** No HOA information was found for the Garden Home subdivision or this property. For a multi-family apartment complex, an HOA or mandatory membership could mean existing or future assessments and liens.
- **Resolution Required:** Contact Garden Home neighborhood association (if any); search Harris County Clerk for HOA lien filings.

### RF-011 — PROPERTY AGE AND CONDITION (1950 MULTI-FAMILY)
- **Risk Level:** 🟡 YELLOW
- **Description:** The property was built in 1950 — 76 years old. Combined with 8 years of potential deferred maintenance due to owner financial distress, there is elevated risk of code violations, structural issues, plumbing/electrical deficiencies, and habitability concerns.
- **Resolution Required:** Physical inspection; Houston Permitting Center code violation check; Phase I ESA recommended.

### RF-012 — UNIT 10 vs. UNIT 1 DISCREPANCY
- **Risk Level:** 🟡 YELLOW
- **Description:** The task input references "UNIT 10" as part of the property address, but the MLS listing on real estate portals is for "APT 1" or "#1." The HCAD account covers the entire parcel (TR 20A), not individual units. It is unclear whether "UNIT 10" is a separate tax parcel, a unit within the building, or a mailing address designation.
- **Resolution Required:** Confirm the exact property scope of HCAD account 061-039-000-0020. Determine whether the tax sale covers the entire building or individual units.

### RF-013 — TENANT OCCUPANCY RISK (APARTMENTS.COM LISTING)
- **Risk Level:** 🟡 YELLOW
- **Description:** Apartments.com lists 1516 W 34th St Houston TX as an active apartment community as of 2026. This suggests active tenants are living in the property.
- **Resolution Required:** Before any acquisition or assignment, determine tenant occupancy status, lease terms, and any tenant protections that apply post-tax sale. Texas Property Code § 21.019 and local ordinances may apply.

---

## GREEN FLAGS (No Immediate Risk Found)

### GF-001 — NO CORPORATE/LLC OWNER FOUND
- **Status:** 🟢 GREEN (CONDITIONAL)
- **Description:** No LLC or corporate entity was found as owner. This avoids entity-dissolution, registered-agent, and corporate-authority chain issues.
- **Condition:** Remains green only if no corporate grantee/grantor appears in the actual deed chain upon Clerk search.

### GF-002 — NO PROBATE FOUND (UNVERIFIED)
- **Status:** 🟢 GREEN (CONDITIONAL)
- **Description:** No probate, estate, or death record found in public web search.
- **Condition:** Remains green only after manual Harris County Probate Court search confirms no pending case.

### GF-003 — NO FEDERAL LAWSUIT FOUND (UNVERIFIED)
- **Status:** 🟢 GREEN (CONDITIONAL)
- **Description:** No federal civil case found for any name variant.
- **Condition:** Remains green only after PACER search.

---

## SUMMARY RISK MATRIX

| Flag ID | Description | Level | Resolved? |
|---|---|---|---|
| RF-001 | Unconfirmed 2023 deed transfer | 🔴 CRITICAL | NO |
| RF-002 | Chain of title unverified | 🔴 CRITICAL | NO |
| RF-003 | Bankruptcy status unverified | 🔴 CRITICAL | NO |
| RF-004 | IRS lien status unknown | 🔴 CRITICAL | NO |
| RF-005 | 8 years tax delinquency | 🟠 MAJOR | NO |
| RF-006 | Adjudged value vs. bid gap | 🟠 MAJOR | NO |
| RF-007 | Multi-family complexity | 🟠 MAJOR | NO |
| RF-008 | Owner name spelling variants | 🟠 MAJOR | NO |
| RF-009 | Out-of-state owner / contact | 🟠 MAJOR | NO |
| RF-010 | HOA status unknown | 🟡 YELLOW | NO |
| RF-011 | 1950 building age / condition | 🟡 YELLOW | NO |
| RF-012 | Unit 10 vs. APT 1 discrepancy | 🟡 YELLOW | NO |
| RF-013 | Active tenant occupancy | 🟡 YELLOW | NO |
| GF-001 | No corporate owner found | 🟢 CONDITIONAL | CONDITIONAL |
| GF-002 | No probate found | 🟢 CONDITIONAL | CONDITIONAL |
| GF-003 | No federal lawsuit found | 🟢 CONDITIONAL | CONDITIONAL |

**Overall Score: 🔴 RED — HIGH RISK**

*Do not spend money on this deal until all 🔴 CRITICAL flags are resolved.*
