"""
Tests for agents/buyer-activity-osint/run.py

Covers:
  • build_column_map for Propwire and deed/export headers
  • detect_format heuristic
  • unmapped_headers
  • _map_row / load_raw_dir against temp CSVs
  • seed matching
  • profile building (with and without seed match)
  • ignored-file reporting
  • end-to-end with workspace-rooted sample data
"""
from __future__ import annotations
import csv
import json
import sys
import tempfile
from io import StringIO
from pathlib import Path

import pytest

# Import the agent as a module — it is a single self-contained file
sys.path.insert(0, str(Path(__file__).parent.parent))
import run as agent


# ═══════════════════════════════════════════════════════════════════════════════
# build_column_map — Propwire
# ═══════════════════════════════════════════════════════════════════════════════

class TestColumnMapPropwire:
    HEADERS = [
        "Buyer Name", "Buyer Company", "Buyer Name 2",
        "Property Address", "City", "State", "Zip",
        "Sale Date", "Sale Price", "Property Type",
        "Financing Type", "Lender Name", "Loan Amount",
        "Beds", "Baths", "Sqft", "Year Built", "County",
    ]

    def test_all_recognised(self):
        m = agent.build_column_map(self.HEADERS)
        assert len(m) == len(self.HEADERS)

    def test_buyer_name(self):
        assert agent.build_column_map(["Buyer Name"])["Buyer Name"] == "buyer_name"

    def test_buyer_company_to_entity(self):
        assert agent.build_column_map(["Buyer Company"])["Buyer Company"] == "buyer_entity"

    def test_sale_price(self):
        assert agent.build_column_map(["Sale Price"])["Sale Price"] == "sale_price"

    def test_financing_type(self):
        assert agent.build_column_map(["Financing Type"])["Financing Type"] == "financing_type"

    def test_no_duplicate_canonical_targets(self):
        m = agent.build_column_map(self.HEADERS)
        vals = list(m.values())
        assert len(vals) == len(set(vals))


# ═══════════════════════════════════════════════════════════════════════════════
# build_column_map — deed/export
# ═══════════════════════════════════════════════════════════════════════════════

class TestColumnMapDeed:
    HEADERS = [
        "grantee_name", "grantee_name_2", "entity_name", "grantor_name",
        "property_address", "property_city", "property_state", "property_zip",
        "county", "recording_date", "consideration_amount", "property_type",
        "financing_type", "lender_name", "loan_amount", "apn",
        "year_built", "sqft",
    ]

    def test_all_recognised(self):
        m = agent.build_column_map(self.HEADERS)
        assert len(m) == len(self.HEADERS)

    def test_grantee_name_to_buyer(self):
        assert agent.build_column_map(["grantee_name"])["grantee_name"] == "buyer_name"

    def test_grantee_name_2(self):
        assert agent.build_column_map(["grantee_name_2"])["grantee_name_2"] == "buyer_name_2"

    def test_entity_name(self):
        assert agent.build_column_map(["entity_name"])["entity_name"] == "buyer_entity"

    def test_recording_date_to_sale_date(self):
        assert agent.build_column_map(["recording_date"])["recording_date"] == "sale_date"

    def test_consideration_amount_to_sale_price(self):
        assert agent.build_column_map(["consideration_amount"])["consideration_amount"] == "sale_price"

    def test_grantor_to_seller(self):
        assert agent.build_column_map(["grantor_name"])["grantor_name"] == "seller_name"


# ═══════════════════════════════════════════════════════════════════════════════
# Alias coverage
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("header,expected", [
    ("Owner",                     "buyer_name"),
    ("owner_name",                "buyer_name"),
    ("Grantee",                   "buyer_name"),
    ("Purchaser",                 "buyer_name"),
    ("Mailing Name",              "buyer_name"),
    ("Co-Buyer",                  "buyer_name_2"),
    ("owner_2",                   "buyer_name_2"),
    ("Buyer Entity",              "buyer_entity"),
    ("Company",                   "buyer_entity"),
    ("Seller",                    "seller_name"),
    ("grantor",                   "seller_name"),
    ("Address",                   "property_address"),
    ("situs_address",             "property_address"),
    ("zip_code",                  "zip"),
    ("postal_code",               "zip"),
    ("situs_zip",                 "zip"),
    ("deed_date",                 "sale_date"),
    ("transfer_date",             "sale_date"),
    ("last_sale_date",            "sale_date"),
    ("closing date",              "sale_date"),
    ("sales_price",               "sale_price"),
    ("purchase_price",            "sale_price"),
    ("transfer_amount",           "sale_price"),
    ("deed_amount",               "sale_price"),
    ("land_use",                  "property_type"),
    ("use_code",                  "property_type"),
    ("Loan Type",                 "financing_type"),
    ("deed_type",                 "financing_type"),
    ("transaction_type",          "financing_type"),
    ("Lender",                    "lender_name"),
    ("mortgagee",                 "lender_name"),
    ("mortgage_amount",           "loan_amount"),
    ("APN",                       "apn"),
    ("parcel_number",             "apn"),
    ("assessor_parcel_number",    "apn"),
    ("Bedrooms",                  "beds"),
    ("Bathrooms",                 "baths"),
    ("Square Feet",               "sqft"),
    ("living_area",               "sqft"),
    ("Year Built",                "year_built"),
    ("year_constructed",          "year_built"),
])
def test_alias(header, expected):
    m = agent.build_column_map([header])
    assert m.get(header) == expected, f"{header!r} → got {m.get(header)!r}, want {expected!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# detect_format / unmapped_headers
# ═══════════════════════════════════════════════════════════════════════════════

def test_detect_propwire():
    assert agent.detect_format(["Buyer Name", "Sale Price"]) == "propwire"

def test_detect_deed():
    assert agent.detect_format(["grantee_name", "recording_date"]) == "deed"

def test_detect_unknown():
    assert agent.detect_format(["apn", "city", "state"]) == "unknown"

def test_unmapped_headers_returns_unknown():
    result = agent.unmapped_headers(["Buyer Name", "WeirdColumn"])
    assert "WeirdColumn" in result
    assert "Buyer Name" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# CSV ingestion helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _tmpdir_with(files: dict[str, str]) -> Path:
    d = Path(tempfile.mkdtemp())
    for name, content in files.items():
        (d / name).write_text(content, encoding="utf-8")
    return d


def _txns_from_csv(content: str) -> list[agent.Transaction]:
    d = _tmpdir_with({"test.csv": content})
    txns, _ = agent.load_raw_dir(d)
    return txns


class TestRowParsing:
    def test_propwire_row_parsed(self):
        txns = _txns_from_csv(
            "Buyer Name,Property Address,Sale Price,Sale Date,Zip\n"
            "Jordan Tate,2345 Pine Rd,89000,2025-01-10,77018\n"
        )
        assert len(txns) == 1
        t = txns[0]
        assert t.buyer_name == "Jordan Tate"
        assert t.sale_price == 89000.0
        assert t.zip == "77018"

    def test_deed_row_parsed(self):
        txns = _txns_from_csv(
            "grantee_name,consideration_amount,recording_date,property_zip\n"
            "TATE JORDAN,89000,2025-01-10,77018\n"
        )
        assert len(txns) == 1
        t = txns[0]
        assert t.buyer_name == "TATE JORDAN"
        assert t.sale_price == 89000.0
        assert t.sale_date == "2025-01-10"

    def test_entity_name_promoted_from_buyer_name(self):
        txns = _txns_from_csv(
            "Buyer Name,Property Address\nSunrise Holdings LLC,123 Oak St\n"
        )
        assert txns[0].buyer_entity is not None

    def test_row_without_buyer_skipped(self):
        txns = _txns_from_csv("Buyer Name,Sale Price\n,145000\n")
        assert len(txns) == 0

    def test_sale_price_dollar_commas_stripped(self):
        txns = _txns_from_csv('Buyer Name,Sale Price\nJane Smith,"$1,250,000"\n')
        assert txns[0].sale_price == 1_250_000.0

    def test_zip_9digit_trimmed_to_5(self):
        txns = _txns_from_csv("Buyer Name,Zip\nJoe Buyer,77008-1234\n")
        assert txns[0].zip == "77008"


# ═══════════════════════════════════════════════════════════════════════════════
# Ignored-file logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestIgnoredFiles:
    def test_non_csv_ignored(self):
        d = _tmpdir_with({"notes.txt": "hello"})
        _, ignored = agent.load_raw_dir(d)
        assert any("not a CSV" in i.reason for i in ignored)

    def test_empty_csv_ignored(self):
        d = _tmpdir_with({"empty.csv": ""})
        _, ignored = agent.load_raw_dir(d)
        assert any(Path(i.path).name == "empty.csv" for i in ignored)

    def test_no_recognised_headers_ignored(self):
        d = _tmpdir_with({"weird.csv": "foo,bar,baz\n1,2,3\n"})
        _, ignored = agent.load_raw_dir(d)
        assert any("no recognised headers" in i.reason for i in ignored)

    def test_no_buyer_column_ignored(self):
        d = _tmpdir_with({"no_buyer.csv": "Sale Price,Sale Date\n145000,2024-01-01\n"})
        _, ignored = agent.load_raw_dir(d)
        assert any("no buyer" in i.reason for i in ignored)

    def test_valid_csv_not_ignored(self):
        d = _tmpdir_with({
            "valid.csv": "Buyer Name,Sale Price\nJohn Doe,100000\n"
        })
        txns, ignored = agent.load_raw_dir(d)
        assert len(txns) == 1
        assert not ignored


# ═══════════════════════════════════════════════════════════════════════════════
# Seed matching
# ═══════════════════════════════════════════════════════════════════════════════

SEEDS = [
    agent.BuyerSeed("BUY-0001", "Marcus Webb",  "Webb Capital Holdings LLC", "active"),
    agent.BuyerSeed("BUY-0002", "Diana Reyes",  "Reyes Rentals LLC",         "active"),
    agent.BuyerSeed("BUY-0003", "Jordan Tate",  None,                        "active"),
]

def test_seed_entity_match():
    s = agent.match_seed("Webb Capital Holdings LLC", None, SEEDS)
    assert s is not None and s.buyer_id == "BUY-0001"

def test_seed_individual_match():
    s = agent.match_seed(None, "Jordan Tate", SEEDS)
    assert s is not None and s.buyer_id == "BUY-0003"

def test_seed_case_insensitive():
    s = agent.match_seed("WEBB CAPITAL HOLDINGS LLC", None, SEEDS)
    assert s is not None and s.buyer_id == "BUY-0001"

def test_seed_no_match_returns_none():
    assert agent.match_seed("Unknown Entity LLC", "Nobody", SEEDS) is None

def test_seed_empty_list_returns_none():
    assert agent.match_seed("Webb Capital Holdings LLC", None, []) is None


# ═══════════════════════════════════════════════════════════════════════════════
# Profile building
# ═══════════════════════════════════════════════════════════════════════════════

def _txn(**kw) -> agent.Transaction:
    defaults = dict(
        source_file="test.csv", fmt="propwire",
        buyer_name=None, buyer_name_2=None, buyer_entity=None,
        seller_name=None, property_address="123 Test St",
        city="Houston", state="TX", zip="77008", county="Harris",
        apn=None, sale_date="2025-01-01", sale_price=100_000.0,
        property_type="SFR", financing_type="Cash",
        lender_name=None, loan_amount=None,
        beds=3, baths=2.0, sqft=1400, year_built=1970,
    )
    defaults.update(kw)
    return agent.Transaction(**defaults)


class TestBuildProfiles:
    def test_profile_without_seed_still_created(self):
        profiles = agent.build_profiles([_txn(buyer_name="Unknown Person")], SEEDS)
        assert len(profiles) == 1
        assert profiles[0].seed_id is None

    def test_profile_with_seed_enriched(self):
        profiles = agent.build_profiles(
            [_txn(buyer_entity="Webb Capital Holdings LLC")], SEEDS
        )
        assert profiles[0].seed_id == "BUY-0001"
        assert profiles[0].seed_status == "active"

    def test_transactions_grouped_by_entity(self):
        txns = [
            _txn(buyer_entity="Webb Capital Holdings LLC", zip="77008"),
            _txn(buyer_entity="Webb Capital Holdings LLC", zip="77009"),
            _txn(buyer_entity="Reyes Rentals LLC",         zip="77010"),
        ]
        profiles = agent.build_profiles(txns, SEEDS)
        assert len(profiles) == 2
        webb = next(p for p in profiles if "Webb" in (p.entity_name or ""))
        assert webb.transaction_count == 2

    def test_price_stats(self):
        txns = [
            _txn(buyer_entity="Alpha LLC", sale_price=100_000.0),
            _txn(buyer_entity="Alpha LLC", sale_price=200_000.0),
        ]
        p = agent.build_profiles(txns, [])[0]
        assert p.price_min == 100_000.0
        assert p.price_max == 200_000.0
        assert p.price_avg == 150_000.0

    def test_sorted_by_transaction_count(self):
        txns = [
            _txn(buyer_entity="Small LLC"),
            _txn(buyer_entity="Big LLC"),
            _txn(buyer_entity="Big LLC"),
        ]
        profiles = agent.build_profiles(txns, [])
        assert profiles[0].transaction_count >= profiles[-1].transaction_count

    def test_entity_only_creates_profile(self):
        profiles = agent.build_profiles([_txn(buyer_name=None, buyer_entity="Solo LLC")], [])
        assert profiles[0].entity_name == "Solo LLC"

    def test_individual_only_creates_profile(self):
        profiles = agent.build_profiles([_txn(buyer_name="Solo Person", buyer_entity=None)], [])
        assert profiles[0].individual_name == "Solo Person"

    def test_empty_input_returns_empty(self):
        assert agent.build_profiles([], SEEDS) == []


# ═══════════════════════════════════════════════════════════════════════════════
# End-to-end with workspace-rooted sample data
# ═══════════════════════════════════════════════════════════════════════════════

def _make_workspace() -> Path:
    """Create a minimal workspace with both CSV formats."""
    ws = Path(tempfile.mkdtemp())
    raw = ws / "data" / "buyer-activity" / "raw"
    raw.mkdir(parents=True)

    (raw / "propwire_sample.csv").write_text(
        "Buyer Name,Buyer Company,Property Address,City,State,Zip,"
        "Sale Date,Sale Price,Property Type,Financing Type\n"
        "Marcus Webb,Webb Capital Holdings LLC,1234 Oak St,Houston,TX,77008,"
        "2024-11-15,145000,SFR,Cash\n"
        "Diana Reyes,Reyes Rentals LLC,5678 Elm Ave,Houston,TX,77009,"
        "2024-12-01,165000,SFR,Conventional\n"
        ",New Build LLC,9012 Maple Dr,Houston,TX,77022,"
        "2025-02-20,220000,MFR,Hard Money\n",
        encoding="utf-8",
    )

    (raw / "deed_export_sample.csv").write_text(
        "grantee_name,entity_name,grantor_name,property_address,"
        "property_city,property_state,property_zip,"
        "recording_date,consideration_amount,property_type,financing_type\n"
        "WEBB MARCUS,WEBB CAPITAL HOLDINGS LLC,SMITH JOHN,1234 OAK ST,"
        "HOUSTON,TX,77008,2024-11-15,145000,SINGLE FAMILY RESIDENTIAL,CASH\n"
        "REYES DIANA,REYES RENTALS LLC,JOHNSON SARAH,5678 ELM AVE,"
        "HOUSTON,TX,77009,2024-12-01,165000,SINGLE FAMILY RESIDENTIAL,CONVENTIONAL\n"
        "TATE JORDAN,,BROWN MIKE,2345 PINE RD,"
        "HOUSTON,TX,77018,2025-01-10,89000,SINGLE FAMILY RESIDENTIAL,CASH\n",
        encoding="utf-8",
    )

    (raw / "not_a_csv.txt").write_text("notes here", encoding="utf-8")
    (raw / "empty.csv").write_text("", encoding="utf-8")
    return ws


class TestEndToEnd:
    def setup_method(self):
        self.ws = _make_workspace()
        raw_dir = self.ws / "data" / "buyer-activity" / "raw"
        self.txns, self.ignored = agent.load_raw_dir(raw_dir)
        self.profiles = agent.build_profiles(self.txns, SEEDS)

    def test_nonzero_transaction_count(self):
        assert len(self.txns) > 0, "eligible_transaction_count should be > 0"

    def test_nonzero_profile_count(self):
        assert len(self.profiles) > 0, "buyer_profiles should be non-empty"

    def test_non_csv_file_in_ignored(self):
        assert any("not a CSV" in i.reason for i in self.ignored)

    def test_empty_csv_in_ignored(self):
        assert any(Path(i.path).name == "empty.csv" for i in self.ignored)

    def test_all_transactions_have_buyer_identifier(self):
        for t in self.txns:
            assert t.buyer_name or t.buyer_entity

    def test_zip_codes_are_5_digits(self):
        for t in self.txns:
            if t.zip:
                assert len(t.zip) == 5 and t.zip.isdigit()

    def test_webb_seed_matched(self):
        webb = next(
            (p for p in self.profiles if p.seed_id == "BUY-0001"),
            None,
        )
        assert webb is not None

    def test_buyer_without_seed_still_has_profile(self):
        no_seed = [p for p in self.profiles if p.seed_id is None]
        assert len(no_seed) > 0

    def test_reports_written(self):
        reports_dir = self.ws / "reports"
        agent.write_reports(self.txns, self.profiles, self.ignored, reports_dir, self.ws)
        assert (reports_dir / "BUYER_ACTIVITY_PROFILES.md").exists()
        assert (reports_dir / "IGNORED_FILES.md").exists()
        summary = json.loads((reports_dir / "ACTIVITY_SUMMARY.json").read_text())
        assert summary["eligible_transaction_count"] == len(self.txns)
        assert len(summary["buyer_profiles"]) == len(self.profiles)
        assert len(summary["ignored_files"]) == len(self.ignored)

    def test_cli_runs_without_error(self):
        rc = agent.main([
            "--workspace-root", str(self.ws),
            "--reports-dir", str(self.ws / "cli_reports"),
            "--dry-run",
        ])
        assert rc == 0
