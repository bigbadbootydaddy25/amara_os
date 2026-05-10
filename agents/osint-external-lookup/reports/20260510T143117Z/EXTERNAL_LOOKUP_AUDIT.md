# OSINT External Lookup Audit

**Run:** `20260510T143117Z`  
**Allowed use:** `lawful_osint_only`  
**Method:** Lawful public-record exports, user-provided CSV/JSON files, inference from enriched data

---

## Gap Reduction Summary

| Metric | Count |
|--------|-------|
| Original missing field slots | 156 |
| Remaining unresolved | 126 |
| Gap reduction | 30 fields |
| Gap reduction % | 19% |

---

## Field Status Breakdown

### Entities

| Status | Count |
|--------|-------|
| `resolved` | 87 |
| `low_confidence` | 0 |
| `inferred` | 18 |
| `stale` | 0 |
| `unresolved` | 48 |

### Properties

| Status | Count |
|--------|-------|
| `resolved` | 75 |
| `low_confidence` | 0 |
| `inferred` | 12 |
| `stale` | 0 |
| `unresolved` | 78 |

---

## Source Files Available

> **No source export files found in `data/osint/sources/`.**
>
> To enrich with public records, place CSV/JSON exports in that directory.
> Supported adapters and their expected filename patterns:

- **County Appraisal District (CAD) Export**: `*cad*.csv`, `*assessor*.csv`, `*appraisal*.csv`, `*cad*.json`
- **County Clerk Recording Export**: `*clerk*.csv`, `*deed*.csv`, `*recording*.csv`, `*grantor*.csv`
- **GIS / APN Parcel Export**: `*gis*.csv`, `*apn*.csv`, `*parcel*.csv`, `*gis*.json`
- **Secretary of State Business Search Export**: `*sos*.csv`, `*secretary*.csv`, `*business_search*.csv`, `*corp_search*.csv`
- **Trustee Sale / Foreclosure Notice Export**: `*trustee*.csv`, `*foreclosure*.csv`, `*notice_of_sale*.csv`, `*nod*.csv`
- **Building Permit Export**: `*permit*.csv`, `*building_permit*.csv`, `*permits*.json`
- **Code Enforcement Export**: `*code_violation*.csv`, `*code_enforcement*.csv`, `*violations*.csv`
- **Tax Delinquency Export**: `*tax_delinquent*.csv`, `*delinquent_tax*.csv`, `*tax_roll*.csv`
- **PACER Federal Court Record (Manual Export)**: `*pacer*.csv`, `*federal_court*.csv`, `*bankruptcy*.csv`
- **PropStream / Propwire Export (Manual)**: `*propstream*.csv`, `*propwire*.csv`, `*prop_export*.csv`

---

## Inference Adapter Results

Fields resolved without external files via inference from existing enriched data:

| entity_id | field | confidence | value_summary |
|-----------|-------|------------|---------------|
| `DP-001` | `estimated_equity` | low | Severely impaired or negative (inferred: distress_score >= 8… |
| `DP-001` | `loan_balance` | low | Delinquent — 97 days past due (inferred from distress_indica… |
| `DP-002` | `estimated_equity` | low | Materially impaired (inferred: distress_score 55-79 indicate… |
| `DP-002` | `loan_balance` | low | Delinquent — 41 days past due (inferred from distress_indica… |
| `DP-003` | `estimated_equity` | low | Severely impaired or negative (inferred: distress_score >= 8… |
| `DP-003` | `loan_balance` | low | Delinquent — 148 days past due (inferred from distress_indic… |
| `DP-004` | `estimated_equity` | low | Materially impaired (inferred: distress_score 55-79 indicate… |
| `OB-001` | `loan_balance` | low | 7 loan(s) in extension (inferred from leverage_indicators.lo… |
| `OB-002` | `loan_balance` | low | 5 loan(s) in extension (inferred from leverage_indicators.lo… |
| `OB-003` | `loan_balance` | low | 2 loan(s) in extension (inferred from leverage_indicators.lo… |
| `SB-001` | `associated_addresses` | medium | ['SW corner of 51st Ave & Dobbins Rd, Phoenix, AZ 85339', '1… |
| `SB-001` | `portfolio_count` | low | 2… |
| `SB-001` | `estimated_equity` | low | Severely impaired or negative (inferred: distress_score >= 8… |
| `SB-002` | `associated_addresses` | medium | ['4102 N 16th St, Phoenix, AZ 85016']… |
| `SB-002` | `portfolio_count` | low | 1… |
| `SB-002` | `estimated_equity` | low | Materially impaired (inferred: distress_score 55-79 indicate… |
| `SB-003` | `associated_addresses` | medium | ['E Ocotillo Rd & S Ellsworth Rd, Queen Creek, AZ 85142']… |
| `SB-003` | `portfolio_count` | low | 1… |
| `1234_jeff_st_dallas_tx_75208` | `zoning_classification` | medium | Mixed-Use / Bishop Arts Urban Development Overlay (Dallas MU… |
| `1236_jeff_st_dallas_tx_75208` | `zoning_classification` | low | Residential Infill (SF-1 or SF-2 likely; verify with Dallas … |
| `1240_jeff_st_dallas_tx_75208` | `zoning_classification` | medium | Mixed-Use / Bishop Arts Urban Development Overlay (Dallas MU… |
| `1244_jeff_st_dallas_tx_75208` | `zoning_classification` | medium | Mixed-Use / Bishop Arts Urban Development Overlay (Dallas MU… |
| `1250_jeff_st_dallas_tx_75208` | `zoning_classification` | medium | Mixed-Use / Bishop Arts Urban Development Overlay (Dallas MU… |
| `1256_jeff_st_dallas_tx_75208` | `zoning_classification` | low | Residential Infill (SF-1 or SF-2 likely; verify with Dallas … |
| `516_n_bishop_ave_dallas_tx_75208` | `zoning_classification` | medium | Mixed-Use / Bishop Arts Urban Development Overlay (Dallas MU… |
| `520_n_bishop_ave_dallas_tx_75208` | `zoning_classification` | medium | Mixed-Use / Bishop Arts Urban Development Overlay (Dallas MU… |
| `420_w_12th_st_dallas_tx_75208` | `zoning_classification` | medium | Commercial Corridor / Trinity Groves Planned Development (CS… |
| `2215_singleton_blvd_dallas_tx_75212` | `zoning_classification` | medium | Commercial Corridor / Trinity Groves Planned Development (CS… |
| `1100_n_zang_blvd_dallas_tx_75208` | `zoning_classification` | medium | Mixed-Use / Bishop Arts Urban Development Overlay (Dallas MU… |
| `802_canty_st_dallas_tx_75203` | `zoning_classification` | low | Residential Infill (SF-1 or SF-2 likely; verify with Dallas … |

---

## Remaining Gaps

Fields that could not be resolved by any available adapter or inference:

| entity_id | type | missing_fields | how_to_resolve |
|-----------|------|----------------|----------------|
| `DP-001` | entity | sos_status, registered_agent, associated_addresses | SOS export, PropStream export, or county deed export |
| `DP-002` | entity | sos_status, registered_agent, associated_addresses | SOS export, PropStream export, or county deed export |
| `DP-003` | entity | sos_status, registered_agent, associated_addresses | SOS export, PropStream export, or county deed export |
| `DP-004` | entity | sos_status, registered_agent, associated_addresses +1 more | SOS export, PropStream export, or county deed export |
| `OB-001` | entity | sos_status, registered_agent, associated_addresses +3 more | SOS export, PropStream export, or county deed export |
| `OB-002` | entity | sos_status, registered_agent, associated_addresses +3 more | SOS export, PropStream export, or county deed export |
| `OB-003` | entity | sos_status, registered_agent, associated_addresses +3 more | SOS export, PropStream export, or county deed export |
| `OB-004` | entity | sos_status, registered_agent, associated_addresses +4 more | SOS export, PropStream export, or county deed export |
| `SB-001` | entity | sos_status, registered_agent, loan_balance | SOS export, PropStream export, or county deed export |
| `SB-002` | entity | sos_status, registered_agent, loan_balance | SOS export, PropStream export, or county deed export |
| `SB-003` | entity | sos_status, registered_agent, estimated_equity +1 more | SOS export, PropStream export, or county deed export |
| `1234_jeff_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +2 more | CAD export, county clerk export, or PropStream export |
| `1236_jeff_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +2 more | CAD export, county clerk export, or PropStream export |
| `1240_jeff_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +2 more | CAD export, county clerk export, or PropStream export |
| `1244_jeff_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +2 more | CAD export, county clerk export, or PropStream export |
| `1250_jeff_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +2 more | CAD export, county clerk export, or PropStream export |
| `1256_jeff_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +2 more | CAD export, county clerk export, or PropStream export |
| `516_n_bishop_ave_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +2 more | CAD export, county clerk export, or PropStream export |
| `520_n_bishop_ave_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +2 more | CAD export, county clerk export, or PropStream export |
| `420_w_12th_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +2 more | CAD export, county clerk export, or PropStream export |
| `422_w_12th_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +3 more | CAD export, county clerk export, or PropStream export |
| `2215_singleton_blvd_dallas_tx_75212` | property | owner_name, assessed_value, last_sale_date +2 more | CAD export, county clerk export, or PropStream export |
| `2219_singleton_blvd_dallas_tx_75212` | property | owner_name, assessed_value, last_sale_date +3 more | CAD export, county clerk export, or PropStream export |
| `1100_n_zang_blvd_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +2 more | CAD export, county clerk export, or PropStream export |
| `802_canty_st_dallas_tx_75203` | property | owner_name, assessed_value, last_sale_date +2 more | CAD export, county clerk export, or PropStream export |
| `806_canty_st_dallas_tx_75203` | property | owner_name, assessed_value, last_sale_date +3 more | CAD export, county clerk export, or PropStream export |

---

## Compliance Notes

- All enriched values carry `allowed_use: lawful_osint_only`
- No credential harvesting, login bypass, or private scraping performed
- Inference values are explicitly labeled `source_type: inferred` and `confidence: low` or `medium`
- Missing values remain `source_type: missing` — no fabrication
- Cache TTL: 30 days | Source staleness threshold: 90 days
