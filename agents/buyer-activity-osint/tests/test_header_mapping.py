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
from datetime import date
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

    def test_new_report_files_written(self):
        reports_dir = self.ws / "reports2"
        agent.write_reports(self.txns, self.profiles, self.ignored, reports_dir, self.ws)
        assert (reports_dir / "RECENT_BUYERS.json").exists()
        assert (reports_dir / "MULTI_PURCHASE_BUYERS.json").exists()
        assert (reports_dir / "BUYER_PURCHASE_HISTORY.md").exists()


# ═══════════════════════════════════════════════════════════════════════════════
# Purchase history — _parse_date
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseDate:
    @pytest.mark.parametrize("raw,expected", [
        ("2025-01-15",     date(2025, 1, 15)),
        ("01/15/2025",     date(2025, 1, 15)),
        ("1/15/2025",      date(2025, 1, 15)),
        ("01-15-2025",     date(2025, 1, 15)),
        ("20250115",       date(2025, 1, 15)),
        ("January 15, 2025", date(2025, 1, 15)),
        ("Jan 15, 2025",   date(2025, 1, 15)),
        ("",               None),
        (None,             None),
        ("not-a-date",     None),
        ("2025-13-01",     None),   # invalid month
    ])
    def test_parse_date_formats(self, raw, expected):
        assert agent._parse_date(raw) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# Purchase history — profile fields
# ═══════════════════════════════════════════════════════════════════════════════

# Fixed reference date so all window calculations are deterministic
_REF = date(2026, 5, 9)


def _prof(txns, seeds=None) -> agent.BuyerActivityProfile:
    """Build profiles with fixed reference date; return first profile."""
    profiles = agent.build_profiles(txns, seeds or [], ref_date=_REF)
    assert profiles, "expected at least one profile"
    return profiles[0]


class TestPurchaseHistoryFields:
    def test_total_purchase_count(self):
        txns = [
            _txn(buyer_entity="Big LLC", sale_date="2025-01-01"),
            _txn(buyer_entity="Big LLC", sale_date="2025-06-01"),
        ]
        p = _prof(txns)
        assert p.total_purchase_count == 2

    def test_recent_counts_within_window(self):
        # One purchase 60 days before ref, one 200 days before ref
        d60  = (date(2026, 3, 10)).isoformat()   # 60d before 2026-05-09
        d200 = (date(2025, 10, 21)).isoformat()  # ~200d before
        txns = [
            _txn(buyer_entity="Big LLC", sale_date=d60),
            _txn(buyer_entity="Big LLC", sale_date=d200),
        ]
        p = _prof(txns)
        assert p.recent_purchase_count_30d == 0
        assert p.recent_purchase_count_90d == 1
        assert p.recent_purchase_count_180d == 1
        assert p.recent_purchase_count_365d == 2

    def test_last_and_first_purchase_date(self):
        txns = [
            _txn(buyer_entity="Alpha LLC", sale_date="2024-03-01"),
            _txn(buyer_entity="Alpha LLC", sale_date="2025-11-01"),
        ]
        p = _prof(txns)
        assert p.first_purchase_date == "2024-03-01"
        assert p.last_purchase_date == "2025-11-01"

    def test_days_since_last_purchase(self):
        # last purchase exactly 100 days before _REF (2026-05-09)
        d = date(2026, 1, 29).isoformat()  # 100 days before 2026-05-09
        txns = [_txn(buyer_entity="Beta LLC", sale_date=d)]
        p = _prof(txns)
        assert p.days_since_last_purchase == 100

    def test_no_date_gives_none(self):
        txns = [_txn(buyer_entity="Ghost LLC", sale_date=None)]
        p = _prof(txns)
        assert p.last_purchase_date is None
        assert p.days_since_last_purchase is None
        assert p.first_purchase_date is None

    def test_multi_purchase_buyer_true(self):
        txns = [
            _txn(buyer_entity="Busy LLC", sale_date="2025-01-01"),
            _txn(buyer_entity="Busy LLC", sale_date="2025-06-01"),
        ]
        p = _prof(txns)
        assert p.multi_purchase_buyer is True

    def test_multi_purchase_buyer_false_for_single(self):
        txns = [_txn(buyer_entity="Quiet LLC", sale_date="2025-01-01")]
        p = _prof(txns)
        assert p.multi_purchase_buyer is False

    def test_repeat_market_buyer_multiple_zips(self):
        txns = [
            _txn(buyer_entity="Wide LLC", zip="77008", sale_date="2025-01-01"),
            _txn(buyer_entity="Wide LLC", zip="77009", sale_date="2025-06-01"),
        ]
        p = _prof(txns)
        assert p.repeat_market_buyer is True

    def test_repeat_market_buyer_false_single_zip(self):
        txns = [
            _txn(buyer_entity="Narrow LLC", zip="77008", sale_date="2025-01-01"),
            _txn(buyer_entity="Narrow LLC", zip="77008", sale_date="2025-06-01"),
        ]
        p = _prof(txns)
        assert p.repeat_market_buyer is False

    def test_purchase_markets_populated(self):
        txns = [
            _txn(buyer_entity="Wide LLC", city="Houston",  sale_date="2025-01-01"),
            _txn(buyer_entity="Wide LLC", city="Dallas",   sale_date="2025-06-01"),
            _txn(buyer_entity="Wide LLC", city="Houston",  sale_date="2025-09-01"),
        ]
        p = _prof(txns)
        assert set(p.purchase_markets) == {"Houston", "Dallas"}

    def test_purchase_zip_codes_populated(self):
        txns = [
            _txn(buyer_entity="ZipCo LLC", zip="77008", sale_date="2025-01-01"),
            _txn(buyer_entity="ZipCo LLC", zip="75201", sale_date="2025-06-01"),
        ]
        p = _prof(txns)
        assert "77008" in p.purchase_zip_codes
        assert "75201" in p.purchase_zip_codes

    def test_purchase_property_types_populated(self):
        txns = [
            _txn(buyer_entity="Prop LLC", property_type="SFR", sale_date="2025-01-01"),
            _txn(buyer_entity="Prop LLC", property_type="MFR", sale_date="2025-06-01"),
        ]
        p = _prof(txns)
        assert set(p.purchase_property_types) == {"MFR", "SFR"}


class TestPurchaseTimingConfidence:
    def test_high_when_all_dated(self):
        txns = [
            _txn(buyer_entity="Dated LLC", sale_date="2025-01-01"),
            _txn(buyer_entity="Dated LLC", sale_date="2025-06-01"),
        ]
        p = _prof(txns)
        assert p.purchase_timing_confidence == "high"

    def test_low_when_no_dates(self):
        txns = [
            _txn(buyer_entity="Ghost LLC", sale_date=None),
            _txn(buyer_entity="Ghost LLC", sale_date=None),
        ]
        p = _prof(txns)
        assert p.purchase_timing_confidence == "low"

    def test_medium_when_partial(self):
        txns = [
            _txn(buyer_entity="Mixed LLC", sale_date="2025-01-01"),
            _txn(buyer_entity="Mixed LLC", sale_date=None),
        ]
        p = _prof(txns)
        assert p.purchase_timing_confidence == "medium"


class TestPurchaseVelocityScore:
    def test_zero_for_no_transactions(self):
        p = agent.build_profiles([], [], ref_date=_REF)
        assert p == []

    def test_single_purchase_is_10(self):
        txns = [_txn(buyer_entity="Solo LLC", sale_date="2025-01-01")]
        p = _prof(txns)
        assert p.purchase_velocity_score == 10.0

    def test_zero_velocity_when_no_dates(self):
        txns = [_txn(buyer_entity="Ghost LLC", sale_date=None)]
        p = _prof(txns)
        assert p.purchase_velocity_score == 0.0

    def test_higher_velocity_for_faster_buyer(self):
        fast = [
            _txn(buyer_entity="Fast LLC", sale_date="2025-01-01"),
            _txn(buyer_entity="Fast LLC", sale_date="2025-01-15"),
            _txn(buyer_entity="Fast LLC", sale_date="2025-02-01"),
        ]
        slow = [
            _txn(buyer_entity="Slow LLC", sale_date="2023-01-01"),
            _txn(buyer_entity="Slow LLC", sale_date="2025-01-01"),
        ]
        p_fast = agent.build_profiles(fast, [], ref_date=_REF)[0]
        p_slow = agent.build_profiles(slow, [], ref_date=_REF)[0]
        assert p_fast.purchase_velocity_score > p_slow.purchase_velocity_score

    def test_velocity_capped_at_100(self):
        txns = [
            _txn(buyer_entity="Mega LLC", sale_date=f"2025-01-{d:02d}")
            for d in range(1, 29)
        ]
        p = _prof(txns)
        assert p.purchase_velocity_score <= 100.0


class TestRecentPurchaseEvidence:
    def test_evidence_only_within_180_days(self):
        d_recent = date(2026, 2, 1).isoformat()   # ~97d before ref
        d_old    = date(2024, 1, 1).isoformat()   # far in past
        txns = [
            _txn(buyer_entity="EvidCo LLC", sale_date=d_recent, property_address="100 New St"),
            _txn(buyer_entity="EvidCo LLC", sale_date=d_old,    property_address="200 Old St"),
        ]
        p = _prof(txns)
        assert len(p.recent_purchase_evidence) == 1
        assert "100 New St" in (p.recent_purchase_evidence[0].get("address") or "")

    def test_evidence_has_required_keys(self):
        d = date(2026, 2, 1).isoformat()
        txns = [_txn(buyer_entity="Keys LLC", sale_date=d)]
        p = _prof(txns)
        ev = p.recent_purchase_evidence[0]
        assert "date" in ev
        assert "address" in ev
        assert "sale_price" in ev
        assert "financing_type" in ev
        assert "source_file" in ev

    def test_evidence_source_file_is_basename(self):
        d = date(2026, 2, 1).isoformat()
        txns = [_txn(buyer_entity="NameCo LLC", sale_date=d, source_file="/long/path/mydata.csv")]
        p = _prof(txns)
        assert p.recent_purchase_evidence[0]["source_file"] == "mydata.csv"

    def test_no_evidence_when_no_recent_purchases(self):
        txns = [_txn(buyer_entity="Old LLC", sale_date="2020-01-01")]
        p = _prof(txns)
        assert p.recent_purchase_evidence == []


class TestNewOutputFiles:
    def setup_method(self):
        self.ws = _make_workspace()
        raw_dir = self.ws / "data" / "buyer-activity" / "raw"
        txns, ignored = agent.load_raw_dir(raw_dir)
        self.profiles = agent.build_profiles(txns, SEEDS, ref_date=_REF)
        self.reports_dir = self.ws / "ph_reports"
        agent.write_reports(txns, self.profiles, ignored, self.reports_dir, self.ws)

    def test_recent_buyers_json_exists(self):
        assert (self.reports_dir / "RECENT_BUYERS.json").exists()

    def test_multi_purchase_buyers_json_exists(self):
        assert (self.reports_dir / "MULTI_PURCHASE_BUYERS.json").exists()

    def test_buyer_purchase_history_md_exists(self):
        assert (self.reports_dir / "BUYER_PURCHASE_HISTORY.md").exists()

    def test_recent_buyers_json_structure(self):
        data = json.loads((self.reports_dir / "RECENT_BUYERS.json").read_text())
        assert "total_recent_buyers" in data
        assert "window_days" in data
        assert "buyers" in data
        assert data["window_days"] == 90

    def test_multi_purchase_buyers_have_count_gte_2(self):
        data = json.loads((self.reports_dir / "MULTI_PURCHASE_BUYERS.json").read_text())
        for buyer in data["buyers"]:
            assert buyer["total_purchase_count"] >= 2

    def test_purchase_history_md_has_table(self):
        md = (self.reports_dir / "BUYER_PURCHASE_HISTORY.md").read_text()
        assert "## " in md
        assert "Total purchases" in md
        assert "Purchase velocity score" in md

    def test_activity_summary_has_new_fields(self):
        data = json.loads((self.reports_dir / "ACTIVITY_SUMMARY.json").read_text())
        if data["buyer_profiles"]:
            bp = data["buyer_profiles"][0]
            assert "total_purchase_count" in bp
            assert "recent_purchase_count_90d" in bp
            assert "purchase_velocity_score" in bp
            assert "multi_purchase_buyer" in bp
            assert "recent_purchase_evidence" in bp

    def test_profiles_sorted_by_recent_activity(self):
        data = json.loads((self.reports_dir / "RECENT_BUYERS.json").read_text())
        buyers = data["buyers"]
        for i in range(len(buyers) - 1):
            assert buyers[i]["acquisition_heat_score"] >= buyers[i + 1]["acquisition_heat_score"]

    def test_activity_summary_has_scoring_fields(self):
        data = json.loads((self.reports_dir / "ACTIVITY_SUMMARY.json").read_text())
        if data["buyer_profiles"]:
            bp = data["buyer_profiles"][0]
            assert "activity_recency_score" in bp
            assert "weighted_buyer_score" in bp
            assert "acquisition_heat_score" in bp
            assert "buyer_state" in bp

    def test_hot_buyers_json_exists(self):
        assert (self.reports_dir / "HOT_BUYERS.json").exists()

    def test_active_buyers_json_exists(self):
        assert (self.reports_dir / "ACTIVE_BUYERS.json").exists()

    def test_buyer_heat_rankings_md_exists(self):
        assert (self.reports_dir / "BUYER_HEAT_RANKINGS.md").exists()

    def test_buyer_heat_rankings_has_table(self):
        md = (self.reports_dir / "BUYER_HEAT_RANKINGS.md").read_text()
        assert "## Rankings" in md
        assert "acquisition_heat_score" in md
        assert "Rank" in md


# ═══════════════════════════════════════════════════════════════════════════════
# Scoring helpers — unit tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestActivityRecencyScore:
    @pytest.mark.parametrize("days,expected", [
        (0,    100.0),
        (15,   100.0),
        (30,   100.0),
        (31,    80.0),
        (90,    80.0),
        (91,    55.0),
        (180,   55.0),
        (181,   30.0),
        (365,   30.0),
        (730,    0.0),   # exactly 2 years → fully decayed
        (1000,   0.0),
        (None,   0.0),
    ])
    def test_recency_score_thresholds(self, days, expected):
        assert agent._activity_recency_score(days) == expected

    def test_recency_decays_between_365_and_730(self):
        s400 = agent._activity_recency_score(400)
        s600 = agent._activity_recency_score(600)
        assert 0.0 < s400 < 15.0
        assert 0.0 < s600 < s400


class TestWeightedBuyerScore:
    def _score(self, **kw):
        defaults = dict(
            cnt_30=0, cnt_90=0, cnt_180=0, total=1,
            multi=False, repeat=False, n_zips=1,
            has_sfr=False, has_cash=False, has_hard_money=False,
            has_land=False, has_distress=False,
        )
        defaults.update(kw)
        return agent._weighted_buyer_score(**defaults)

    def test_zero_for_minimal_buyer(self):
        s = self._score()
        assert 0.0 <= s <= 100.0

    def test_30d_purchase_boosts_score(self):
        base  = self._score()
        with_ = self._score(cnt_30=1)
        assert with_ > base

    def test_multi_purchase_adds_points(self):
        assert self._score(multi=True) > self._score(multi=False)

    def test_hard_money_adds_more_than_cash(self):
        hm   = self._score(has_hard_money=True)
        cash = self._score(has_cash=True)
        assert hm > cash

    def test_distress_adds_points(self):
        assert self._score(has_distress=True) > self._score(has_distress=False)

    def test_score_capped_at_100(self):
        s = self._score(
            cnt_30=5, cnt_90=5, cnt_180=5, total=20,
            multi=True, repeat=True, n_zips=1,
            has_sfr=True, has_cash=True, has_hard_money=True,
            has_land=True, has_distress=True,
        )
        assert s <= 100.0

    def test_zip_concentration_bonus(self):
        # 10 purchases in 1 ZIP scores higher than 10 in 10 ZIPs
        concentrated = self._score(total=10, n_zips=1)
        spread       = self._score(total=10, n_zips=10)
        assert concentrated > spread


class TestAcquisitionHeatScore:
    def test_high_recency_dominates(self):
        # Active buyer (recency=100) vs dormant (recency=0) same weighted
        active  = agent._acquisition_heat_score(100.0, 50.0, 20.0, 20)
        dormant = agent._acquisition_heat_score(0.0,   50.0, 20.0, 500)
        assert active > dormant

    def test_decay_applied_beyond_365(self):
        no_decay  = agent._acquisition_heat_score(30.0, 30.0, 10.0, 300)
        with_decay = agent._acquisition_heat_score(30.0, 30.0, 10.0, 730)
        assert with_decay < no_decay

    def test_score_capped_at_100(self):
        assert agent._acquisition_heat_score(100.0, 100.0, 100.0, 5) <= 100.0

    def test_score_is_zero_for_all_zero_inputs(self):
        assert agent._acquisition_heat_score(0.0, 0.0, 0.0, None) == 0.0

    def test_max_decay_is_50_percent(self):
        # At 3 years (1095 days): decay = min(0.5, (730/365)*0.25) = min(0.5, 0.5) = 0.5
        no_decay  = agent._acquisition_heat_score(30.0, 30.0, 10.0, 0)
        max_decay = agent._acquisition_heat_score(30.0, 30.0, 10.0, 1095)
        assert max_decay >= no_decay * 0.45   # at most ~50% reduction


class TestBuyerState:
    @pytest.mark.parametrize("cnt_30,cnt_90,cnt_365,total,expected", [
        (1, 1, 1, 2, "HOT"),
        (0, 1, 1, 2, "ACTIVE"),
        (0, 0, 1, 1, "WARM"),
        (0, 0, 0, 3, "COLD"),
        (0, 0, 0, 1, "DORMANT"),
        (0, 0, 0, 0, "DORMANT"),
    ])
    def test_buyer_state_logic(self, cnt_30, cnt_90, cnt_365, total, expected):
        assert agent._buyer_state(cnt_30, cnt_90, cnt_365, total) == expected


class TestRankingIntegration:
    """Verify that recent active buyers outrank large dormant buyers."""

    def _build(self, entity, sale_date, n=1, zip_="77008"):
        return [_txn(buyer_entity=entity, sale_date=sale_date,
                     financing_type="Cash", property_type="SFR", zip=zip_)
                for _ in range(n)]

    def test_30d_buyer_beats_dormant_whale(self):
        """1 purchase in 30d should outrank 10 purchases all >2 years ago."""
        d_recent = date(2026, 4, 20).isoformat()   # ~19 days before _REF
        d_old    = "2023-01-01"
        recent_txns = self._build("Fresh LLC",   d_recent)
        whale_txns  = self._build("Whale Corp",  d_old, n=10)
        profiles = agent.build_profiles(recent_txns + whale_txns, [], ref_date=_REF)
        top = profiles[0]
        assert top.display_name == "Fresh LLC"
        assert top.buyer_state  == "HOT"

    def test_hot_beats_active_beats_warm(self):
        d_10d  = date(2026, 4, 29).isoformat()  # 10d before ref
        d_60d  = date(2026, 3, 10).isoformat()  # 60d before ref
        d_300d = date(2025, 7, 13).isoformat()  # ~300d before ref
        hot    = self._build("Hot LLC",    d_10d)
        active = self._build("Active LLC", d_60d)
        warm   = self._build("Warm LLC",   d_300d)
        profiles = agent.build_profiles(hot + active + warm, [], ref_date=_REF)
        states = [p.buyer_state for p in profiles]
        assert states[0] == "HOT"
        assert states[1] == "ACTIVE"
        assert states[2] == "WARM"

    def test_acquisition_heat_score_present_and_positive(self):
        txns = [_txn(buyer_entity="ScoreCo LLC", sale_date="2025-01-01")]
        p = _prof(txns)
        assert p.acquisition_heat_score >= 0.0
        assert p.activity_recency_score >= 0.0
        assert p.weighted_buyer_score   >= 0.0

    def test_profiles_sorted_by_heat_score_descending(self):
        d_recent = date(2026, 4, 20).isoformat()
        d_old    = "2023-06-01"
        txns = (
            self._build("Old Buyer LLC", d_old,    n=5) +
            self._build("New Buyer LLC", d_recent, n=1)
        )
        profiles = agent.build_profiles(txns, [], ref_date=_REF)
        scores = [p.acquisition_heat_score for p in profiles]
        assert scores == sorted(scores, reverse=True)

    def test_buyer_state_on_profile(self):
        d = date(2026, 4, 20).isoformat()
        txns = [_txn(buyer_entity="Hot Co LLC", sale_date=d)]
        p = agent.build_profiles(txns, [], ref_date=_REF)[0]
        assert p.buyer_state == "HOT"

    def test_signal_detection_sfr_cash(self):
        txns = [_txn(buyer_entity="Signal LLC",
                     property_type="SFR", financing_type="Cash",
                     sale_date="2025-01-01")]
        p = _prof(txns)
        assert p.weighted_buyer_score > 0.0

    def test_hard_money_buyer_scores_higher_than_conv(self):
        hm   = [_txn(buyer_entity="HM LLC",   financing_type="Hard Money", sale_date="2025-01-01")]
        conv = [_txn(buyer_entity="Conv LLC",  financing_type="Conventional", sale_date="2025-01-01")]
        p_hm   = agent.build_profiles(hm,   [], ref_date=_REF)[0]
        p_conv = agent.build_profiles(conv, [], ref_date=_REF)[0]
        assert p_hm.weighted_buyer_score > p_conv.weighted_buyer_score


class TestNewRankingOutputFiles:
    def setup_method(self):
        self.ws = _make_workspace()
        raw_dir = self.ws / "data" / "buyer-activity" / "raw"
        txns, ignored = agent.load_raw_dir(raw_dir)
        self.profiles = agent.build_profiles(txns, SEEDS, ref_date=_REF)
        self.reports_dir = self.ws / "rank_reports"
        agent.write_reports(txns, self.profiles, ignored, self.reports_dir, self.ws)

    def test_hot_buyers_json_created(self):
        assert (self.reports_dir / "HOT_BUYERS.json").exists()

    def test_active_buyers_json_created(self):
        assert (self.reports_dir / "ACTIVE_BUYERS.json").exists()

    def test_buyer_heat_rankings_md_created(self):
        assert (self.reports_dir / "BUYER_HEAT_RANKINGS.md").exists()

    def test_hot_buyers_definition_field(self):
        data = json.loads((self.reports_dir / "HOT_BUYERS.json").read_text())
        assert "definition" in data
        assert "30" in data["definition"]

    def test_active_buyers_superset_of_hot(self):
        hot    = json.loads((self.reports_dir / "HOT_BUYERS.json").read_text())
        active = json.loads((self.reports_dir / "ACTIVE_BUYERS.json").read_text())
        assert active["total_active_buyers"] >= hot["total_hot_buyers"]

    def test_heat_rankings_has_state_summary(self):
        md = (self.reports_dir / "BUYER_HEAT_RANKINGS.md").read_text()
        assert "## State Summary" in md
        assert "HOT" in md
        assert "DORMANT" in md

    def test_heat_rankings_sorted_by_heat(self):
        data = json.loads((self.reports_dir / "ACTIVE_BUYERS.json").read_text())
        buyers = data["buyers"]
        for i in range(len(buyers) - 1):
            assert buyers[i]["acquisition_heat_score"] >= buyers[i + 1]["acquisition_heat_score"]

    def test_all_profiles_have_buyer_state(self):
        data = json.loads((self.reports_dir / "ACTIVITY_SUMMARY.json").read_text())
        valid = {"HOT", "ACTIVE", "WARM", "COLD", "DORMANT"}
        for bp in data["buyer_profiles"]:
            assert bp["buyer_state"] in valid

    def test_multi_purchase_sorted_by_heat(self):
        data = json.loads((self.reports_dir / "MULTI_PURCHASE_BUYERS.json").read_text())
        buyers = data["buyers"]
        for i in range(len(buyers) - 1):
            assert buyers[i]["acquisition_heat_score"] >= buyers[i + 1]["acquisition_heat_score"]
