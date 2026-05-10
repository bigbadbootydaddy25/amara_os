# OSINT Compliance Audit

**Run:** `20260510T134621Z`  
**Allowed use:** `lawful_osint_only`  
**Sources:** public records, broker leads, internal manual exports

---

## Summary

| Metric | Count |
|--------|-------|
| Enriched entities | 11 |
| Enriched properties | 15 |
| Queued for enrichment | 26 |
| Total provenance fields | 318 |
| Fields with source | 162 |
| Fields missing source | 156 |
| Fill rate | 51% |

---

## Source Type Breakdown

| source_type | field_count |
|-------------|-------------|
| `broker_lead` | 75 |
| `internal_record` | 87 |
| `missing` | 156 |

---

## Compliance Notes

- All values carry `allowed_use: lawful_osint_only`
- No fabricated values — missing data is marked `source_type: missing`
- Internal records sourced from `data/portfolio-distress/` manual exports
- Broker leads sourced from `data/deal-leads/raw/`
- Public record fields (SOS, assessed value, liens, registered agent) require
  external integration and are queued with `source_type: missing`

---

## Enrichment Queue

| entity_id | type | missing_fields | priority |
|-----------|------|----------------|----------|
| `DP-001` | entity | sos_status, registered_agent, associated_addresses +2 more | high |
| `DP-002` | entity | sos_status, registered_agent, associated_addresses +2 more | high |
| `DP-003` | entity | sos_status, registered_agent, associated_addresses +2 more | high |
| `DP-004` | entity | sos_status, registered_agent, associated_addresses +2 more | high |
| `OB-001` | entity | sos_status, registered_agent, associated_addresses +4 more | high |
| `OB-002` | entity | sos_status, registered_agent, associated_addresses +4 more | high |
| `OB-003` | entity | sos_status, registered_agent, associated_addresses +4 more | high |
| `OB-004` | entity | sos_status, registered_agent, associated_addresses +4 more | high |
| `SB-001` | entity | sos_status, registered_agent, associated_addresses +3 more | high |
| `SB-002` | entity | sos_status, registered_agent, associated_addresses +3 more | high |
| `SB-003` | entity | sos_status, registered_agent, associated_addresses +3 more | high |
| `1234_jeff_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `1236_jeff_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `1240_jeff_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `1244_jeff_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `1250_jeff_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `1256_jeff_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `516_n_bishop_ave_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `520_n_bishop_ave_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `420_w_12th_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `422_w_12th_st_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `2215_singleton_blvd_dallas_tx_75212` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `2219_singleton_blvd_dallas_tx_75212` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `1100_n_zang_blvd_dallas_tx_75208` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `802_canty_st_dallas_tx_75203` | property | owner_name, assessed_value, last_sale_date +3 more | high |
| `806_canty_st_dallas_tx_75203` | property | owner_name, assessed_value, last_sale_date +3 more | high |
