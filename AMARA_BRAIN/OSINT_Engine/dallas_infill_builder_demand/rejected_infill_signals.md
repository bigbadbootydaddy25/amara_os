# REJECTED INFILL SIGNALS
## AMARA OS — Dallas Infill Builder Demand Swarm
### Contradiction Agent Review
**Generated:** 2026-05-15T18:50:27Z

---

## PURPOSE

This file documents all findings that were REJECTED or marked UNVERIFIED by the Contradiction Agent. Rejected signals must NOT be used in scoring, targeting, or downstream disposition decisions.

---

## SECTION 1: REJECTED BUILDER RECORDS

| Entity | Claim | Reason Rejected |
|---|---|---|
| **Lennar at Bishop Arts — 520 W 8th St (225 units)** | Surfaced in AI-generated search summary claiming a 225-unit Lennar project at Bishop Arts | No verifiable source URL; no corroborating press report; could not confirm project name, address, or unit count. REJECTED — treat as UNKNOWN until confirmed via city permit records. |
| **StoryBuilt "Jolene I" — 507 W Commerce St (290 units)** | Same AI-generated summary origin; 290-unit StoryBuilt project at this address | No corroborating press or permit source found. StoryBuilt is a real verified builder but this specific project/address/unit count is UNVERIFIED. REJECTED until confirmed via DallasNow permit portal. |
| **Hawthorne Homes — 25-unit BTR infill (Dallas Medical District)** | BTR infill search summary mentioned this builder and project | No verifiable URL or independent press confirmation found. REJECTED until verifiable. |
| **Bridge Tower / Teasley Crossing** | BTR developer active in DFW | Confirmed as BTR but located in Denton, TX — outside ALL target ZIPs. Not relevant to Dallas infill corridors. EXCLUDED. |
| **Box Investment Group** | Infill industrial developer | Confirmed active in Carrollton, TX; product type is warehouse/industrial, not residential infill. EXCLUDED — not a residential infill builder. |
| **Oak Cliff Design & Construction (Jon & MJ Moreau)** | Listed as Oak Cliff infill operator | General contractor focused on renovation/restoration of existing homes; not new infill construction or townhome development. EXCLUDED from builder list. |
| **The Oak Cliff Renovators** | Listed as Oak Cliff infill operator | General contractor focused on remodeling/restoration; not a new infill builder. EXCLUDED. |
| **Legacy Classic Homes (in target ZIPs)** | Custom SFR builder active in Dallas infill | Price point ($750K–$4M+) misaligned with South/West Dallas affordable infill corridors. Single source only. Marked LOW confidence — not used in scoring for 75215/75216/75217. |
| **NexMetro / Avilla Homes (in target urban ZIPs)** | BTR developer with 16 DFW communities | All known communities are suburban/exurban. No evidence of activity in target ZIPs 75215–75232. EXCLUDED from target ZIP scoring. |
| **Republic Property Group (in target urban ZIPs)** | BTR SFR developer, 600+ units DFW | Confirmed active near Celina/Light Farms only. No confirmed activity in urban infill target ZIPs. EXCLUDED from target ZIP scoring. |
| **Urban Genesis — 2901 Borger St** | 176-unit Singleton Highline project | Project name and address surfaced but no deed record, acquisition date, or permit number confirmed via this search layer. Marked PARTIAL — not used in high-confidence scoring. |
| **Texas Heavenly Homes delivery timeline** | Project claimed to be on track | City Council denied $3M federal grant April 2024 citing builder's failure to meet prior $500K grant obligations. Project status DISPUTED. Do not treat as verified active delivery. |

---

## SECTION 2: REJECTED / UNVERIFIED PERMIT RECORDS

| Signal | Reason Rejected |
|---|---|
| Individual residential permit records by permit number for ZIPs 75217, 75227, 75210, 75215, 75216, 75232 | Dallas OpenData API and DallasNow/Accela portal both returned HTTP 403 Forbidden to all automated requests. No individual permit numbers were retrieved. Data NOT fabricated. Requires direct portal access. |
| Any permit address/number produced by AI search summaries without a corroborating URL | Not accepted. AI-generated summaries can hallucinate permit data. Every permit record in verified_infill_permits.csv has a real source URL. |
| Demolition permit records for 75217, 75227 (Rylie, Pleasant Grove, Urbandale) | No public aggregated permit data retrieved via web search. Dallas OpenData and DallasNow require direct database query — not accessible via web search. |
| Specific GIS demo permit heat maps for Oak Cliff / Fair Park 2025 | Dallas GIS hub has FY23-24 building permit layers but not directly queryable via web search. |

---

## SECTION 3: REJECTED ACQUISITION SIGNALS

| Signal | Reason Rejected |
|---|---|
| Specific deed/document numbers for builder LLC lot purchases in 75215–75217 | Dallas County Clerk records (dallas.tx.publicsearch.us) and DCAD require direct search by address/owner — not accessible via web search. No entity-specific transactions surfaced. |
| Named builder LLC lot acquisitions in 75232, 75210 (Wheatley, Cedar Crest) | Only generic new construction listings found (Ashton Woods, Mattamy Homes at Buckner Terrace — 75210 area). No lot-level acquisition records confirmed. |
| West Dallas LLC teardown-lot acquisitions (specific addresses) | Pattern confirmed from news sources but individual property addresses and deed record document numbers NOT retrieved. Cannot list specific addresses without verification. |

---

## SECTION 4: REJECTED REDEVELOPMENT / POLICY SIGNALS

| Signal Queried | Finding | Reason Rejected |
|---|---|---|
| HUD Choice Neighborhoods Grant for Fair Park/South Dallas | NOT FOUND as a current active grant | The SDFP area is a Neighborhood Revitalization Strategy Area (NRSA) — enables CDBG funds — but is NOT a HUD Choice Neighborhoods grant. These are different programs. The NRSA designation is real and verified; the Choice Neighborhoods claim is REJECTED. |
| Standalone citywide ADU ordinance (post-SDFP) | UNVERIFIED as standalone citywide policy | ForwardDallas 2.0 proposed citywide ADU by-right; critics challenged it; final ADU overlay status NOT confirmed separately from SDFP. The SDFP ADU rights are real and verified for 75215/75210 only. |
| DCAD ZIP-level infill pressure data (75217, 75227) | NOT PUBLICLY AVAILABLE in aggregated form | DCAD does not publish neighborhood-specific infill redevelopment metrics. Raw data requires purchase/access from DCAD Data Products. Cannot extrapolate ZIP-specific scores from aggregate data. |
| ForwardDallas implementation rezoning active in 75217/75227 | NOT YET ACTIVE as of search date | These ZIPs are lower on the implementation priority list vs. South Dallas/Oak Cliff corridors per research results. |
| Dallas Planning Commission specific infill votes for South Dallas 2025 | NOT FOUND specifically | City Plan Commission meets regularly but no South Dallas-only infill votes surfaced in search. Cases proceed through routine CPC agenda. Not independently verifiable via web search. |

---

## SECTION 5: DATA GAPS (NOT REJECTED — PENDING VERIFICATION)

These are NOT rejected; they are open research tasks requiring direct database access:

| Gap | Action Required |
|---|---|
| Individual permit records (75217, 75227, 75215, 75210, 75216, 75232) | Direct API query: https://www.dallasopendata.com/api/views/e7gq-4sah/rows.csv OR DallasNow portal: https://aca-prod.accela.com/DALLASTX/ |
| Demo permit records by ZIP | Dallas OpenData demo permits or Dallas GIS Hub layer: https://egisdata-dallasgis.hub.arcgis.com/datasets/cod-demolition-permits |
| LLC lot acquisition records (Dallas County deed records) | Direct query at https://dallas.tx.publicsearch.us — search by grantee entity name or address range |
| DCAD land value trends by ZIP | https://www.dallascad.org/dataproducts.aspx — purchase data products |
| Ashton Woods / Mattamy Homes permit counts in 75210 | DallasNow permit portal search |
| StoryBuilt "Jolene I" / "507 W Commerce St" permit verification | DallasNow permit portal search by address |

---

*Last updated: 2026-05-15T18:50:27Z*
*Contradiction Agent review: COMPLETE*
