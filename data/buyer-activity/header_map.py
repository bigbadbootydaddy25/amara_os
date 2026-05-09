"""
Header normalisation for buyer-activity CSVs.

Supports two source formats:
  • Propwire  — title-cased headers with spaces
                e.g. "Buyer Name", "Sale Price", "Financing Type"
  • Deed/export — snake_case from county exports or PropStream deed pulls
                  e.g. "grantee_name", "consideration_amount", "recording_date"

All keys in _RAW_MAP are lowercase + whitespace-collapsed.
"""
from __future__ import annotations
import re

# ── Canonical internal field names ────────────────────────────────────────────
CANONICAL = frozenset({
    "buyer_name",
    "buyer_name_2",
    "buyer_entity",
    "seller_name",
    "property_address",
    "city",
    "state",
    "zip",
    "county",
    "apn",
    "sale_date",
    "sale_price",
    "property_type",
    "financing_type",
    "lender_name",
    "loan_amount",
    "beds",
    "baths",
    "sqft",
    "year_built",
})

# ── Raw header → canonical field ──────────────────────────────────────────────
_RAW_MAP: dict[str, str] = {
    # ── buyer / grantee (primary) ─────────────────────────────────────────────
    "buyer name":                   "buyer_name",
    "buyer_name":                   "buyer_name",
    "buyer 1 name":                 "buyer_name",
    "buyer_1_name":                 "buyer_name",
    "buyer name 1":                 "buyer_name",
    "buyer1":                       "buyer_name",
    "grantee name":                 "buyer_name",
    "grantee_name":                 "buyer_name",
    "grantee full name":            "buyer_name",
    "grantee_full_name":            "buyer_name",
    "grantee 1":                    "buyer_name",
    "grantee_1":                    "buyer_name",
    "grantee":                      "buyer_name",
    "buyer":                        "buyer_name",
    "purchaser":                    "buyer_name",
    "owner name":                   "buyer_name",
    "owner_name":                   "buyer_name",
    "owner":                        "buyer_name",
    "owner 1":                      "buyer_name",
    "owner_1":                      "buyer_name",
    "mailing name":                 "buyer_name",

    # ── buyer / grantee (secondary) ───────────────────────────────────────────
    "buyer name 2":                 "buyer_name_2",
    "buyer_name_2":                 "buyer_name_2",
    "buyer 2 name":                 "buyer_name_2",
    "buyer_2_name":                 "buyer_name_2",
    "buyer2":                       "buyer_name_2",
    "grantee name 2":               "buyer_name_2",
    "grantee_name_2":               "buyer_name_2",
    "grantee 2":                    "buyer_name_2",
    "grantee_2":                    "buyer_name_2",
    "co-buyer":                     "buyer_name_2",
    "co buyer":                     "buyer_name_2",
    "owner 2":                      "buyer_name_2",
    "owner_2":                      "buyer_name_2",

    # ── buyer entity / company ────────────────────────────────────────────────
    "buyer company":                "buyer_entity",
    "buyer_company":                "buyer_entity",
    "buyer entity":                 "buyer_entity",
    "buyer_entity":                 "buyer_entity",
    "entity name":                  "buyer_entity",
    "entity_name":                  "buyer_entity",
    "company":                      "buyer_entity",
    "company name":                 "buyer_entity",
    "company_name":                 "buyer_entity",
    "organization":                 "buyer_entity",
    "owner entity":                 "buyer_entity",
    "owner_entity":                 "buyer_entity",

    # ── seller / grantor ──────────────────────────────────────────────────────
    "grantor name":                 "seller_name",
    "grantor_name":                 "seller_name",
    "seller name":                  "seller_name",
    "seller_name":                  "seller_name",
    "seller":                       "seller_name",
    "grantor":                      "seller_name",

    # ── property address ──────────────────────────────────────────────────────
    "property address":             "property_address",
    "property_address":             "property_address",
    "address":                      "property_address",
    "site address":                 "property_address",
    "situs address":                "property_address",
    "situs_address":                "property_address",
    "mailing address":              "property_address",
    "street address":               "property_address",
    "street_address":               "property_address",

    "city":                         "city",
    "property city":                "city",
    "property_city":                "city",
    "situs city":                   "city",
    "situs_city":                   "city",

    "state":                        "state",
    "property state":               "state",
    "property_state":               "state",
    "situs state":                  "state",
    "situs_state":                  "state",

    "zip":                          "zip",
    "zip code":                     "zip",
    "zip_code":                     "zip",
    "postal code":                  "zip",
    "postal_code":                  "zip",
    "property zip":                 "zip",
    "property_zip":                 "zip",
    "situs zip":                    "zip",
    "situs_zip":                    "zip",

    "county":                       "county",
    "property county":              "county",
    "property_county":              "county",

    # ── APN / parcel ──────────────────────────────────────────────────────────
    "apn":                          "apn",
    "parcel number":                "apn",
    "parcel_number":                "apn",
    "parcel id":                    "apn",
    "parcel_id":                    "apn",
    "assessor parcel number":       "apn",
    "assessor_parcel_number":       "apn",
    "tax id":                       "apn",
    "tax_id":                       "apn",
    "folio":                        "apn",
    "folio number":                 "apn",
    "folio_number":                 "apn",
    "account number":               "apn",
    "account_number":               "apn",

    # ── sale date ─────────────────────────────────────────────────────────────
    "sale date":                    "sale_date",
    "sale_date":                    "sale_date",
    "recording date":               "sale_date",
    "recording_date":               "sale_date",
    "deed date":                    "sale_date",
    "deed_date":                    "sale_date",
    "transfer date":                "sale_date",
    "transfer_date":                "sale_date",
    "close date":                   "sale_date",
    "close_date":                   "sale_date",
    "closing date":                 "sale_date",
    "closing_date":                 "sale_date",
    "document date":                "sale_date",
    "document_date":                "sale_date",
    "last sale date":               "sale_date",
    "last_sale_date":               "sale_date",
    "sold date":                    "sale_date",
    "sold_date":                    "sale_date",

    # ── sale price ────────────────────────────────────────────────────────────
    "sale price":                   "sale_price",
    "sale_price":                   "sale_price",
    "sales price":                  "sale_price",
    "sales_price":                  "sale_price",
    "consideration amount":         "sale_price",
    "consideration_amount":         "sale_price",
    "purchase price":               "sale_price",
    "purchase_price":               "sale_price",
    "sold price":                   "sale_price",
    "sold_price":                   "sale_price",
    "transfer amount":              "sale_price",
    "transfer_amount":              "sale_price",
    "deed amount":                  "sale_price",
    "deed_amount":                  "sale_price",

    # ── property type ─────────────────────────────────────────────────────────
    "property type":                "property_type",
    "property_type":                "property_type",
    "type":                         "property_type",
    "use type":                     "property_type",
    "use_type":                     "property_type",
    "land use":                     "property_type",
    "land_use":                     "property_type",
    "use code":                     "property_type",
    "use_code":                     "property_type",
    "property class":               "property_type",
    "property_class":               "property_type",
    "property use":                 "property_type",
    "property_use":                 "property_type",
    "improvement type":             "property_type",
    "improvement_type":             "property_type",

    # ── financing type ────────────────────────────────────────────────────────
    "financing type":               "financing_type",
    "financing_type":               "financing_type",
    "loan type":                    "financing_type",
    "loan_type":                    "financing_type",
    "deed type":                    "financing_type",
    "deed_type":                    "financing_type",
    "transaction type":             "financing_type",
    "transaction_type":             "financing_type",
    "funding type":                 "financing_type",
    "funding_type":                 "financing_type",
    "instrument type":              "financing_type",
    "instrument_type":              "financing_type",

    # ── lender / loan ─────────────────────────────────────────────────────────
    "lender name":                  "lender_name",
    "lender_name":                  "lender_name",
    "lender":                       "lender_name",
    "mortgage company":             "lender_name",
    "mortgage_company":             "lender_name",
    "bank":                         "lender_name",
    "bank name":                    "lender_name",
    "bank_name":                    "lender_name",
    "mortgagee":                    "lender_name",

    "loan amount":                  "loan_amount",
    "loan_amount":                  "loan_amount",
    "mortgage amount":              "loan_amount",
    "mortgage_amount":              "loan_amount",
    "loan balance":                 "loan_amount",
    "loan_balance":                 "loan_amount",
    "open mortgage":                "loan_amount",
    "open_mortgage":                "loan_amount",

    # ── property details ──────────────────────────────────────────────────────
    "beds":                         "beds",
    "bedrooms":                     "beds",
    "bd":                           "beds",
    "bed":                          "beds",
    "# beds":                       "beds",
    "# bedrooms":                   "beds",

    "baths":                        "baths",
    "bathrooms":                    "baths",
    "ba":                           "baths",
    "bath":                         "baths",
    "# baths":                      "baths",
    "# bathrooms":                  "baths",
    "total baths":                  "baths",
    "total_baths":                  "baths",

    "sqft":                         "sqft",
    "sq ft":                        "sqft",
    "square feet":                  "sqft",
    "square_feet":                  "sqft",
    "living area":                  "sqft",
    "living_area":                  "sqft",
    "building size":                "sqft",
    "building_size":                "sqft",
    "heated area":                  "sqft",
    "heated_area":                  "sqft",
    "gross area":                   "sqft",
    "gross_area":                   "sqft",

    "year built":                   "year_built",
    "year_built":                   "year_built",
    "built":                        "year_built",
    "yr built":                     "year_built",
    "yr_built":                     "year_built",
    "year constructed":             "year_built",
    "year_constructed":             "year_built",
}


# ── Public API ────────────────────────────────────────────────────────────────

def _normalise_key(raw: str) -> str:
    """Lowercase, strip outer whitespace, collapse inner whitespace."""
    return re.sub(r"\s+", " ", raw.strip().lower())


def build_column_map(headers: list[str]) -> dict[str, str]:
    """
    Map raw CSV headers to canonical field names.

    Returns {raw_header: canonical_field} for every recognised header.
    First-write wins — duplicate canonical targets are skipped.
    """
    result: dict[str, str] = {}
    seen_canonical: set[str] = set()
    for h in headers:
        key = _normalise_key(h)
        canonical = _RAW_MAP.get(key)
        if canonical and canonical not in seen_canonical:
            result[h] = canonical
            seen_canonical.add(canonical)
    return result


def detect_format(headers: list[str]) -> str:
    """
    Classify a CSV as 'propwire', 'deed', or 'unknown'.

    Propwire: title-case headers with spaces ("Buyer Name").
    Deed:     snake_case all-lowercase headers ("grantee_name").
    """
    snake = sum(1 for h in headers if "_" in h and h == h.lower())
    spaced = sum(1 for h in headers if " " in h)
    if snake > spaced:
        return "deed"
    if spaced > 0:
        return "propwire"
    return "unknown"


def unmapped_headers(headers: list[str]) -> list[str]:
    """Return headers that had no canonical mapping."""
    mapped = set(build_column_map(headers).keys())
    return [h for h in headers if h not in mapped]
