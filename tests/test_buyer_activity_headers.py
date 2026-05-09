"""
Tests for data/buyer-activity — header mapping, ingestion, and profile building.

Covers:
  • build_column_map() for Propwire-style headers
  • build_column_map() for deed/export-style headers
  • detect_format() heuristic
  • unmapped_headers() round-trip
  • load_raw_dir() against the bundled sample CSVs
  • Profile building without any entity seed (requirement 4)
  • Ignored-file reporting (requirement 5)
"""
from __future__ import annotations
import csv
import io
import sys
import tempfile
from pathlib import Path

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_BUYER_ACTIVITY = Path(__file__).parent.parent / "data" / "buyer-activity"
sys.path.insert(0, str(_BUYER_ACTIVITY))

from header_map import build_column_map, detect_format, unmapped_headers, CANONICAL
from ingest import load_raw_dir, Transaction
from seeds import BuyerSeed, match_seed, load_seeds
from profiles import build_profiles, BuyerActivityProfile


# ═══════════════════════════════════════════════════════════════════════════════
# header_map — build_column_map
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildColumnMapPropwire:
    """Propwire-style: title-case headers with spaces."""

    HEADERS = [
        "Buyer Name", "Buyer Company", "Buyer Name 2",
        "Property Address", "City", "State", "Zip",
        "Sale Date", "Sale Price", "Property Type",
        "Financing Type", "Lender Name", "Loan Amount",
        "Beds", "Baths", "Sqft", "Year Built", "County",
    ]

    def test_all_recognised(self):
        col_map = build_column_map(self.HEADERS)
        assert set(col_map.values()) <= CANONICAL

    def test_buyer_name(self):
        col_map = build_column_map(["Buyer Name"])
        assert col_map["Buyer Name"] == "buyer_name"

    def test_buyer_company_maps_to_entity(self):
        col_map = build_column_map(["Buyer Company"])
        assert col_map["Buyer Company"] == "buyer_entity"

    def test_buyer_name_2(self):
        col_map = build_column_map(["Buyer Name 2"])
        assert col_map["Buyer Name 2"] == "buyer_name_2"

    def test_sale_price(self):
        col_map = build_column_map(["Sale Price"])
        assert col_map["Sale Price"] == "sale_price"

    def test_financing_type(self):
        col_map = build_column_map(["Financing Type"])
        assert col_map["Financing Type"] == "financing_type"

    def test_zip_code(self):
        col_map = build_column_map(["Zip Code"])
        assert col_map["Zip Code"] == "zip"

    def test_no_duplicate_canonical_targets(self):
        col_map = build_column_map(self.HEADERS)
        vals = list(col_map.values())
        assert len(vals) == len(set(vals))


class TestBuildColumnMapDeed:
    """Deed/export-style: snake_case lowercase headers."""

    HEADERS = [
        "grantee_name", "grantee_name_2", "entity_name", "grantor_name",
        "property_address", "property_city", "property_state", "property_zip",
        "county", "recording_date", "consideration_amount", "property_type",
        "financing_type", "lender_name", "loan_amount", "apn",
        "year_built", "sqft",
    ]

    def test_all_recognised(self):
        col_map = build_column_map(self.HEADERS)
        assert set(col_map.values()) <= CANONICAL

    def test_grantee_name_maps_to_buyer(self):
        col_map = build_column_map(["grantee_name"])
        assert col_map["grantee_name"] == "buyer_name"

    def test_grantee_name_2(self):
        col_map = build_column_map(["grantee_name_2"])
        assert col_map["grantee_name_2"] == "buyer_name_2"

    def test_entity_name(self):
        col_map = build_column_map(["entity_name"])
        assert col_map["entity_name"] == "buyer_entity"

    def test_recording_date_maps_to_sale_date(self):
        col_map = build_column_map(["recording_date"])
        assert col_map["recording_date"] == "sale_date"

    def test_consideration_amount_maps_to_sale_price(self):
        col_map = build_column_map(["consideration_amount"])
        assert col_map["consideration_amount"] == "sale_price"

    def test_grantor_name_maps_to_seller(self):
        col_map = build_column_map(["grantor_name"])
        assert col_map["grantor_name"] == "seller_name"

    def test_property_zip_maps_to_zip(self):
        col_map = build_column_map(["property_zip"])
        assert col_map["property_zip"] == "zip"

    def test_property_city_maps_to_city(self):
        col_map = build_column_map(["property_city"])
        assert col_map["property_city"] == "city"


class TestBuildColumnMapAliases:
    """Additional alias coverage for both formats."""

    @pytest.mark.parametrize("header,expected", [
        ("Owner",                    "buyer_name"),
        ("owner_name",               "buyer_name"),
        ("Grantee",                  "buyer_name"),
        ("Purchaser",                "buyer_name"),
        ("Mailing Name",             "buyer_name"),
        ("owner",                    "buyer_name"),
        ("Co-Buyer",                 "buyer_name_2"),
        ("owner_2",                  "buyer_name_2"),
        ("Buyer Entity",             "buyer_entity"),
        ("buyer_entity",             "buyer_entity"),
        ("Company",                  "buyer_entity"),
        ("Seller",                   "seller_name"),
        ("grantor",                  "seller_name"),
        ("Address",                  "property_address"),
        ("situs_address",            "property_address"),
        ("Zip",                      "zip"),
        ("zip_code",                 "zip"),
        ("postal_code",              "zip"),
        ("situs_zip",                "zip"),
        ("Sale Date",                "sale_date"),
        ("deed_date",                "sale_date"),
        ("transfer_date",            "sale_date"),
        ("last_sale_date",           "sale_date"),
        ("closing date",             "sale_date"),
        ("Sale Price",               "sale_price"),
        ("sales_price",              "sale_price"),
        ("purchase_price",           "sale_price"),
        ("transfer_amount",          "sale_price"),
        ("deed_amount",              "sale_price"),
        ("Property Type",            "property_type"),
        ("land_use",                 "property_type"),
        ("use_code",                 "property_type"),
        ("Loan Type",                "financing_type"),
        ("deed_type",                "financing_type"),
        ("transaction_type",         "financing_type"),
        ("Lender",                   "lender_name"),
        ("mortgagee",                "lender_name"),
        ("mortgage_amount",          "loan_amount"),
        ("APN",                      "apn"),
        ("parcel_number",            "apn"),
        ("assessor_parcel_number",   "apn"),
        ("Bedrooms",                 "beds"),
        ("Bathrooms",                "baths"),
        ("Square Feet",              "sqft"),
        ("living_area",              "sqft"),
        ("Year Built",               "year_built"),
        ("year_constructed",         "year_built"),
    ])
    def test_alias(self, header, expected):
        col_map = build_column_map([header])
        assert col_map.get(header) == expected, (
            f"Expected {header!r} → {expected!r}, got {col_map.get(header)!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# detect_format
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectFormat:
    def test_propwire_detected(self):
        assert detect_format(["Buyer Name", "Sale Price", "Property Type"]) == "propwire"

    def test_deed_detected(self):
        assert detect_format(["grantee_name", "recording_date", "property_zip"]) == "deed"

    def test_unknown_when_no_spaces_or_underscores(self):
        assert detect_format(["apn", "city", "state"]) == "unknown"

    def test_mixed_leans_toward_majority(self):
        # 3 snake_case vs 1 space → deed
        fmt = detect_format(["grantee_name", "recording_date", "property_zip", "Sale Price"])
        assert fmt == "deed"


# ═══════════════════════════════════════════════════════════════════════════════
# unmapped_headers
# ═══════════════════════════════════════════════════════════════════════════════

class TestUnmappedHeaders:
    def test_no_unmapped_when_all_recognised(self):
        headers = ["Buyer Name", "Sale Price", "Property Type"]
        assert unmapped_headers(headers) == []

    def test_returns_unknown_headers(self):
        headers = ["Buyer Name", "SomeWeirdColumn", "AnotherUnknown"]
        result = unmapped_headers(headers)
        assert "SomeWeirdColumn" in result
        assert "AnotherUnknown" in result
        assert "Buyer Name" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# ingest — load_raw_dir against sample files
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_RAW = _BUYER_ACTIVITY / "raw"


@pytest.mark.skipif(not SAMPLE_RAW.exists(), reason="raw/ directory not present")
class TestLoadRawDirSamples:
    def test_propwire_sample_yields_transactions(self):
        txns, _ = load_raw_dir(SAMPLE_RAW)
        assert len(txns) > 0

    def test_all_transactions_have_buyer_identifier(self):
        txns, _ = load_raw_dir(SAMPLE_RAW)
        for t in txns:
            assert t.buyer_name or t.buyer_entity, (
                f"Transaction from {t.source_file} has no buyer identifier"
            )

    def test_sale_prices_parsed_as_floats(self):
        txns, _ = load_raw_dir(SAMPLE_RAW)
        priced = [t for t in txns if t.sale_price is not None]
        assert len(priced) > 0
        for t in priced:
            assert isinstance(t.sale_price, float)

    def test_zip_codes_are_5_digits(self):
        txns, _ = load_raw_dir(SAMPLE_RAW)
        for t in txns:
            if t.zip:
                assert len(t.zip) == 5 and t.zip.isdigit(), f"Bad ZIP: {t.zip}"

    def test_entity_names_extracted(self):
        txns, _ = load_raw_dir(SAMPLE_RAW)
        entities = [t.buyer_entity for t in txns if t.buyer_entity]
        assert len(entities) > 0

    def test_no_ignored_for_sample_csvs(self):
        _, ignored = load_raw_dir(SAMPLE_RAW)
        csv_ignored = [i for i in ignored if Path(i.path).suffix.lower() == ".csv"]
        assert csv_ignored == [], f"Sample CSVs were unexpectedly ignored: {csv_ignored}"


# ═══════════════════════════════════════════════════════════════════════════════
# ingest — ignored file logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestIgnoredFiles:
    def _make_dir(self, files: dict[str, str]) -> Path:
        d = Path(tempfile.mkdtemp())
        for name, content in files.items():
            (d / name).write_text(content, encoding="utf-8")
        return d

    def test_non_csv_file_ignored(self):
        d = self._make_dir({"notes.txt": "some notes"})
        _, ignored = load_raw_dir(d)
        assert any("not a CSV" in i.reason for i in ignored)

    def test_empty_csv_ignored(self):
        d = self._make_dir({"empty.csv": ""})
        _, ignored = load_raw_dir(d)
        assert any(Path(i.path).name == "empty.csv" for i in ignored)

    def test_csv_with_no_recognised_headers_ignored(self):
        content = "foo,bar,baz\n1,2,3\n"
        d = self._make_dir({"weird.csv": content})
        _, ignored = load_raw_dir(d)
        assert any("no recognised headers" in i.reason for i in ignored)

    def test_csv_with_no_buyer_column_ignored(self):
        # Has recognised headers but none are buyer fields
        content = "Sale Price,Sale Date,Property Type\n145000,2024-11-15,SFR\n"
        d = self._make_dir({"no_buyer.csv": content})
        _, ignored = load_raw_dir(d)
        assert any("no buyer" in i.reason for i in ignored)

    def test_ignored_reason_explains_what_was_found(self):
        content = "AlienColumn1,AlienColumn2\nval1,val2\n"
        d = self._make_dir({"alien.csv": content})
        _, ignored = load_raw_dir(d)
        assert ignored
        assert ignored[0].reason  # non-empty explanation

    def test_valid_csv_not_in_ignored(self):
        content = (
            "Buyer Name,Property Address,Sale Price,Sale Date\n"
            "John Doe,123 Main St,100000,2024-01-01\n"
        )
        d = self._make_dir({"valid.csv": content})
        txns, ignored = load_raw_dir(d)
        assert len(txns) == 1
        assert not ignored


# ═══════════════════════════════════════════════════════════════════════════════
# ingest — row-level parsing
# ═══════════════════════════════════════════════════════════════════════════════

class TestRowParsing:
    def _txns_from_csv(self, content: str) -> list[Transaction]:
        d = Path(tempfile.mkdtemp())
        (d / "test.csv").write_text(content, encoding="utf-8")
        txns, _ = load_raw_dir(d)
        return txns

    def test_sale_price_stripped_of_dollar_and_commas(self):
        # Dollar+comma values must be quoted in CSV so the parser doesn't split them
        txns = self._txns_from_csv(
            'Buyer Name,Sale Price\nJane Smith,"$1,250,000"\n'
        )
        assert txns[0].sale_price == 1_250_000.0

    def test_entity_name_in_buyer_name_promoted_to_entity(self):
        txns = self._txns_from_csv(
            "Buyer Name,Property Address\nSunrise Holdings LLC,123 Oak St\n"
        )
        assert txns[0].buyer_entity is not None
        assert "Holdings" in txns[0].buyer_entity

    def test_row_without_buyer_skipped(self):
        txns = self._txns_from_csv(
            "Buyer Name,Sale Price\n,145000\n"
        )
        assert len(txns) == 0

    def test_deed_style_grantee_ingested(self):
        txns = self._txns_from_csv(
            "grantee_name,consideration_amount,recording_date\n"
            "TATE JORDAN,89000,2025-01-10\n"
        )
        assert len(txns) == 1
        assert txns[0].buyer_name == "TATE JORDAN"
        assert txns[0].sale_price == 89000.0
        assert txns[0].sale_date == "2025-01-10"

    def test_zip_extracted_from_5digit(self):
        txns = self._txns_from_csv(
            "Buyer Name,Zip\nJoe Buyer,77008\n"
        )
        assert txns[0].zip == "77008"

    def test_zip_extracted_from_9digit_format(self):
        txns = self._txns_from_csv(
            "Buyer Name,Zip\nJoe Buyer,77008-1234\n"
        )
        assert txns[0].zip == "77008"


# ═══════════════════════════════════════════════════════════════════════════════
# seeds — matching
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeedMatching:
    SEEDS = [
        BuyerSeed("BUY-0001", "Marcus Webb",  "Webb Capital Holdings LLC", "active", ["77008"]),
        BuyerSeed("BUY-0002", "Diana Reyes",  "Reyes Rentals LLC",         "active", ["77009"]),
        BuyerSeed("BUY-0003", "Jordan Tate",  None,                        "active", ["77018"]),
    ]

    def test_entity_name_exact_match(self):
        seed = match_seed("Webb Capital Holdings LLC", None, self.SEEDS)
        assert seed is not None
        assert seed.buyer_id == "BUY-0001"

    def test_individual_name_exact_match(self):
        seed = match_seed(None, "Jordan Tate", self.SEEDS)
        assert seed is not None
        assert seed.buyer_id == "BUY-0003"

    def test_entity_match_case_insensitive(self):
        seed = match_seed("WEBB CAPITAL HOLDINGS LLC", None, self.SEEDS)
        assert seed is not None
        assert seed.buyer_id == "BUY-0001"

    def test_no_match_returns_none(self):
        seed = match_seed("Unknown Entity LLC", "Jane Unknown", self.SEEDS)
        assert seed is None

    def test_empty_seeds_returns_none(self):
        seed = match_seed("Webb Capital Holdings LLC", None, [])
        assert seed is None


# ═══════════════════════════════════════════════════════════════════════════════
# profiles — build_profiles
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildProfiles:
    SEEDS = [
        BuyerSeed("BUY-0001", "Marcus Webb", "Webb Capital Holdings LLC", "active", ["77008"]),
    ]

    def _txn(self, **kwargs) -> Transaction:
        defaults = dict(
            source_file="test.csv", fmt="propwire",
            buyer_name=None, buyer_name_2=None, buyer_entity=None,
            seller_name=None, property_address="123 Test St",
            city="Houston", state="TX", zip="77008", county="Harris",
            apn=None, sale_date="2025-01-01", sale_price=100000.0,
            property_type="SFR", financing_type="Cash",
            lender_name=None, loan_amount=None,
            beds=3, baths=2.0, sqft=1400, year_built=1970,
        )
        defaults.update(kwargs)
        return Transaction(**defaults)

    def test_profiles_created_without_seed_match(self):
        txns = [self._txn(buyer_name="Unknown Buyer")]
        profiles = build_profiles(txns, self.SEEDS)
        assert len(profiles) == 1
        assert profiles[0].seed_id is None  # no seed match — profile still created

    def test_profiles_created_with_seed_match(self):
        txns = [self._txn(buyer_entity="Webb Capital Holdings LLC")]
        profiles = build_profiles(txns, self.SEEDS)
        assert len(profiles) == 1
        assert profiles[0].seed_id == "BUY-0001"
        assert profiles[0].seed_status == "active"

    def test_transactions_grouped_by_entity(self):
        txns = [
            self._txn(buyer_entity="Webb Capital Holdings LLC", zip="77008"),
            self._txn(buyer_entity="Webb Capital Holdings LLC", zip="77009"),
            self._txn(buyer_entity="Reyes Rentals LLC",         zip="77010"),
        ]
        profiles = build_profiles(txns, self.SEEDS)
        # Two distinct buyers
        assert len(profiles) == 2
        webb = next(p for p in profiles if "Webb" in (p.entity_name or ""))
        assert webb.transaction_count == 2

    def test_price_stats_computed(self):
        txns = [
            self._txn(buyer_entity="Alpha LLC", sale_price=100000.0),
            self._txn(buyer_entity="Alpha LLC", sale_price=200000.0),
        ]
        profiles = build_profiles(txns, [])
        p = profiles[0]
        assert p.price_min == 100000.0
        assert p.price_max == 200000.0
        assert p.price_avg == 150000.0

    def test_sorted_by_transaction_count_descending(self):
        txns = [
            self._txn(buyer_entity="Small LLC"),
            self._txn(buyer_entity="Big LLC"),
            self._txn(buyer_entity="Big LLC"),
            self._txn(buyer_entity="Big LLC"),
        ]
        profiles = build_profiles(txns, [])
        assert profiles[0].transaction_count >= profiles[1].transaction_count

    def test_zip_codes_unique_and_sorted(self):
        txns = [
            self._txn(buyer_entity="Multi LLC", zip="77022"),
            self._txn(buyer_entity="Multi LLC", zip="77008"),
            self._txn(buyer_entity="Multi LLC", zip="77008"),
        ]
        profiles = build_profiles(txns, [])
        assert profiles[0].zip_codes == ["77008", "77022"]

    def test_empty_transactions_returns_empty(self):
        profiles = build_profiles([], self.SEEDS)
        assert profiles == []

    def test_entity_only_row_creates_profile(self):
        # buyer_name is None — only buyer_entity is set
        txns = [self._txn(buyer_name=None, buyer_entity="Entity Only LLC")]
        profiles = build_profiles(txns, [])
        assert len(profiles) == 1
        assert profiles[0].entity_name == "Entity Only LLC"

    def test_individual_only_row_creates_profile(self):
        # buyer_entity is None — only buyer_name is set
        txns = [self._txn(buyer_name="Solo Person", buyer_entity=None)]
        profiles = build_profiles(txns, [])
        assert len(profiles) == 1
        assert profiles[0].individual_name == "Solo Person"


# ═══════════════════════════════════════════════════════════════════════════════
# End-to-end: sample files produce expected counts
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not SAMPLE_RAW.exists(), reason="raw/ directory not present")
class TestEndToEnd:
    def test_sample_produces_nonzero_count(self):
        txns, ignored = load_raw_dir(SAMPLE_RAW)
        profiles = build_profiles(txns, [])
        assert len(txns) > 0, "eligible_transaction_count should be > 0"
        assert len(profiles) > 0, "buyer_profiles should be non-empty"

    def test_multiple_sources_consolidated_per_buyer(self):
        # Both sample files have the same buyers → they should be merged
        txns, _ = load_raw_dir(SAMPLE_RAW)
        profiles = build_profiles(txns, [])
        webb = next(
            (p for p in profiles if "webb" in (p.entity_name or "").lower()),
            None,
        )
        assert webb is not None
        assert webb.transaction_count >= 2  # appears in both CSVs

    def test_profiles_match_seeds_when_available(self):
        from seeds import BuyerSeed
        seeds = [
            BuyerSeed("BUY-0001", "Marcus Webb", "Webb Capital Holdings LLC", "active"),
        ]
        txns, _ = load_raw_dir(SAMPLE_RAW)
        profiles = build_profiles(txns, seeds)
        webb = next(
            (p for p in profiles if p.seed_id == "BUY-0001"),
            None,
        )
        assert webb is not None
