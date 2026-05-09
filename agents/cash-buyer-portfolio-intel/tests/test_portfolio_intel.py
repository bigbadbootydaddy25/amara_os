"""
Tests for agents/cash-buyer-portfolio-intel/run.py

Covers:
- CSV header normalisation (PropStream title-case + snake_case aliases)
- Encoding-resilient reader (cp1252 byte 0x97 regression)
- Note extraction (estimated_value, loan_balance, equity, screenshot paths)
- Portfolio aggregation (financial sums, equity_ratio, deduplication)
- All six scoring functions with boundary conditions
- Dispo priority formula weights
- Output file presence and structure (all 5 required files)
- Activity summary + ownership graph enrichment
- Evidence audit trail populated for every value source
"""
from __future__ import annotations

import csv
import io
import json
import sys
from dataclasses import fields
from datetime import date
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_DIR))

import run as R
from run import (
    CashBuyerPortfolio,
    FileResult,
    ManualNote,
    PropertyRecord,
    build_portfolios,
    ingest_csv_dir,
    ingest_notes_dir,
    load_activity_summary,
    load_ownership_graph,
    parse_note_file,
    read_csv_rows,
    write_reports,
    _score_confidence,
    _score_liquidity,
    _score_buying_capacity,
    _score_leverage_risk,
    _score_activity,
    _score_asset_match,
    _score_dispo_priority,
    _norm_equity_pct,
    _buyer_key,
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _csv_bytes(rows: list[dict], encoding: str = "utf-8") -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode(encoding)


def _write_csv(tmp_path: Path, name: str, rows: list[dict],
               encoding: str = "utf-8") -> Path:
    p = tmp_path / name
    p.write_bytes(_csv_bytes(rows, encoding))
    return p


REF_DATE = date(2026, 5, 9)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CSV header normalisation
# ═══════════════════════════════════════════════════════════════════════════════

class TestHeaderNormalisation:
    """All PropStream title-case and snake_case variants map to canonical names."""

    def _ingest(self, tmp_path: Path, rows: list[dict]) -> list[PropertyRecord]:
        _write_csv(tmp_path, "data.csv", rows)
        recs, _ = ingest_csv_dir(tmp_path)
        return recs

    def test_propstream_title_case(self, tmp_path):
        rows = [{"Owner Name": "Alice LLC", "Estimated Value": "300000",
                 "Open Loan Balance": "50000", "Last Sale Price": "280000",
                 "Property Address": "123 Main St", "City": "Dallas",
                 "State": "TX", "Zip Code": "75201", "County": "Dallas",
                 "Property Type": "SFR", "Occupancy Status": "Owner Occupied",
                 "Purchase Method": "Cash", "Last Sale Date": "2025-03-15"}]
        recs = self._ingest(tmp_path, rows)
        assert len(recs) == 1
        r = recs[0]
        assert r.owner_name == "Alice LLC"
        assert r.estimated_value == 300_000.0
        assert r.open_loan_balance == 50_000.0
        assert r.last_sale_price == 280_000.0
        assert r.property_address == "123 Main St"
        assert r.zip == "75201"
        assert r.county == "Dallas"
        assert r.property_type == "SFR"
        assert r.occupancy == "Owner Occupied"
        assert r.purchase_method == "Cash"
        assert r.last_sale_date == "2025-03-15"

    def test_snake_case_aliases(self, tmp_path):
        rows = [{"owner_name": "Beta Holdings", "estimated_value": "500000",
                 "open_loan_balance": "0", "last_sale_price": "490000",
                 "property_address": "456 Oak Ave", "zip_code": "75202",
                 "purchase_method": "cash", "last_sale_date": "2026-01-10"}]
        recs = self._ingest(tmp_path, rows)
        assert recs[0].owner_name == "Beta Holdings"
        assert recs[0].estimated_value == 500_000.0
        assert recs[0].open_loan_balance == 0.0

    def test_avm_alias(self, tmp_path):
        rows = [{"owner": "Gamma LLC", "avm": "425000"}]
        recs = self._ingest(tmp_path, rows)
        assert recs[0].estimated_value == 425_000.0

    def test_zestimate_alias(self, tmp_path):
        rows = [{"owner": "Delta Corp", "zestimate": "310000"}]
        recs = self._ingest(tmp_path, rows)
        assert recs[0].estimated_value == 310_000.0

    def test_linked_properties_aliases(self, tmp_path):
        rows = [{"owner": "Epsilon LLC", "properties owned": "12"}]
        recs = self._ingest(tmp_path, rows)
        assert recs[0].linked_properties_count == 12

    def test_total_liens_alias(self, tmp_path):
        rows = [{"owner": "Zeta Inc", "total liens": "120000"}]
        recs = self._ingest(tmp_path, rows)
        assert recs[0].open_loan_balance == 120_000.0

    def test_dom_alias(self, tmp_path):
        rows = [{"owner": "Eta LLC", "days on market": "45"}]
        recs = self._ingest(tmp_path, rows)
        assert recs[0].dom == 45.0

    def test_equity_pct_normalised_from_0_100(self, tmp_path):
        """equity % column with value '72' should be stored as 0.72."""
        rows = [{"owner": "Theta Corp", "equity %": "72"}]
        recs = self._ingest(tmp_path, rows)
        assert recs[0].equity_pct == pytest.approx(0.72, abs=0.001)

    def test_equity_pct_already_0_1(self, tmp_path):
        """equity_ratio column with '0.65' should be stored as 0.65."""
        rows = [{"owner": "Iota LLC", "equity ratio": "0.65"}]
        recs = self._ingest(tmp_path, rows)
        assert recs[0].equity_pct == pytest.approx(0.65, abs=0.001)

    def test_dollar_sign_stripped_from_sale_price(self, tmp_path):
        rows = [{"owner": "Kappa LLC", "sale price": "$250,000"}]
        recs = self._ingest(tmp_path, rows)
        assert recs[0].last_sale_price == 250_000.0

    def test_row_without_owner_skipped(self, tmp_path):
        rows = [{"address": "789 Pine St", "estimated value": "200000"}]
        recs = self._ingest(tmp_path, rows)
        assert recs == []

    def test_unrecognised_headers_skipped(self, tmp_path):
        rows = [{"foo": "bar", "baz": "qux"}]
        _write_csv(tmp_path, "unrecog.csv", rows)
        recs, skipped = ingest_csv_dir(tmp_path)
        assert recs == []
        assert any("no recognised" in (r.skip_reason or "") for r in skipped)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Encoding resilience
# ═══════════════════════════════════════════════════════════════════════════════

class TestEncodingResilience:
    def test_cp1252_em_dash_regression(self, tmp_path):
        """Byte 0x97 (cp1252 em dash) must succeed with encoding_used='cp1252'."""
        header = b"owner,estimated value\r\n"
        value  = b"Smith\x97Brothers LLC,350000\r\n"
        path   = tmp_path / "cp1252.csv"
        path.write_bytes(header + value)

        result = read_csv_rows(path)

        assert result.skipped is False
        assert result.encoding_used == "cp1252"
        assert "Smith" in result.rows[0]["owner"]

    def test_utf8_bom_read_first(self, tmp_path):
        content = "owner,estimated value\r\nBOM LLC,400000\r\n"
        path = tmp_path / "bom.csv"
        path.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))

        result = read_csv_rows(path)
        assert result.encoding_used == "utf-8-sig"
        assert result.rows[0]["owner"] == "BOM LLC"

    def test_ingest_dir_does_not_crash_on_bad_file(self, tmp_path):
        # Good file
        _write_csv(tmp_path, "good.csv",
                   [{"owner": "Good LLC", "estimated value": "100000"}])
        # Force all-fail via patched ENCODINGS
        original = R.ENCODINGS
        try:
            R.ENCODINGS = ("utf-8-sig", "utf-8")   # type: ignore[attr-defined]
            bad = tmp_path / "bad.csv"
            bad.write_bytes(b"owner,val\r\nSmith\x97,99\r\n")
            recs, skipped = ingest_csv_dir(tmp_path)
        finally:
            R.ENCODINGS = original                  # type: ignore[attr-defined]

        bad_names = {Path(r.path).name for r in skipped if r.skipped}
        assert "bad.csv" in bad_names
        assert any(r.owner_name == "Good LLC" for r in recs)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Note / screenshot extraction
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoteExtraction:
    def _note(self, tmp_path: Path, text: str) -> ManualNote:
        p = tmp_path / "note.md"
        p.write_text(text, encoding="utf-8")
        result = parse_note_file(p)
        assert result is not None
        return result

    def test_estimated_value_extracted(self, tmp_path):
        n = self._note(tmp_path, "owner: Alpha LLC\nestimated value: $450,000")
        assert n.estimated_value == 450_000.0

    def test_market_value_alias(self, tmp_path):
        n = self._note(tmp_path, "owner: Beta LLC\nmarket value: $510000")
        assert n.estimated_value == 510_000.0

    def test_open_loan_balance_extracted(self, tmp_path):
        n = self._note(tmp_path, "owner: Gamma LLC\nopen loan balance: $80,000")
        assert n.open_loan_balance == 80_000.0

    def test_equity_extracted(self, tmp_path):
        n = self._note(tmp_path, "owner: Delta LLC\nequity: $370,000")
        assert n.equity == 370_000.0

    def test_equity_pct_normalised(self, tmp_path):
        n = self._note(tmp_path, "owner: Epsilon LLC\nequity ratio: 82%")
        assert n.equity_pct == pytest.approx(0.82, abs=0.001)

    def test_screenshot_paths_captured(self, tmp_path):
        text = (
            "owner: Zeta LLC\n"
            "screenshot: /Users/user/Downloads/propstream_export.png\n"
            "image: notes/snapshot2.jpg\n"
        )
        n = self._note(tmp_path, text)
        assert len(n.screenshot_paths) == 2
        assert any("propstream_export.png" in s for s in n.screenshot_paths)

    def test_linked_properties_count_extracted(self, tmp_path):
        n = self._note(tmp_path, "owner: Eta LLC\nproperties owned: 7")
        assert n.linked_properties_count == 7

    def test_no_owner_returns_none(self, tmp_path):
        p = tmp_path / "noowner.md"
        p.write_text("estimated value: $300000", encoding="utf-8")
        result = parse_note_file(p)
        assert result is None

    def test_purchase_method_extracted(self, tmp_path):
        n = self._note(tmp_path, "owner: Theta LLC\npurchase method: Cash")
        assert n.purchase_method is not None
        assert "Cash" in n.purchase_method

    def test_ingest_notes_dir_skips_non_note_files(self, tmp_path):
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        (tmp_path / "note.md").write_text("owner: Iota LLC\nestimated value: $200000",
                                           encoding="utf-8")
        notes = ingest_notes_dir(tmp_path)
        assert len(notes) == 1
        assert notes[0].owner_name == "Iota LLC"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Financial aggregation
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinancialAggregation:
    def _build(self, recs, notes=None, act=None, graph=None):
        return build_portfolios(
            recs, notes or [], act or {}, graph or {},
            ref_date=REF_DATE,
        )

    def _rec(self, owner, ev=None, olb=None, eq=None, ep=None, sp=None,
             sd=None, addr=None, zip_=None, county=None, ptype=None, pm=None,
             dom=None, linked=None):
        return PropertyRecord(
            source_file="test.csv", source_type="portfolio_export",
            owner_name=owner, property_address=addr,
            city=None, state="TX", zip=zip_, county=county,
            apn=None, estimated_value=ev, open_loan_balance=olb,
            equity=eq, equity_pct=ep, ltv=None,
            last_sale_price=sp, last_sale_date=sd,
            dom=dom, property_type=ptype, occupancy=None,
            purchase_method=pm, linked_properties_count=linked,
        )

    def test_total_estimated_value_summed(self):
        recs = [
            self._rec("Alpha LLC", ev=200_000),
            self._rec("Alpha LLC", ev=150_000),
        ]
        ps = self._build(recs)
        assert len(ps) == 1
        assert ps[0].total_estimated_value == pytest.approx(350_000.0)

    def test_total_loan_balance_summed(self):
        recs = [
            self._rec("Beta LLC", ev=200_000, olb=80_000),
            self._rec("Beta LLC", ev=150_000, olb=40_000),
        ]
        ps = self._build(recs)
        assert ps[0].total_open_loan_balance == pytest.approx(120_000.0)

    def test_equity_computed_from_value_minus_loans(self):
        recs = [self._rec("Gamma LLC", ev=400_000, olb=100_000)]
        ps = self._build(recs)
        assert ps[0].total_portfolio_equity == pytest.approx(300_000.0)
        assert ps[0].equity_ratio == pytest.approx(0.75, abs=0.001)

    def test_equity_ratio_from_pct_when_no_value(self):
        recs = [self._rec("Delta LLC", ep=0.60)]
        ps = self._build(recs)
        assert ps[0].equity_ratio == pytest.approx(0.60, abs=0.001)

    def test_average_sale_price(self):
        recs = [
            self._rec("Epsilon LLC", sp=200_000),
            self._rec("Epsilon LLC", sp=300_000),
        ]
        ps = self._build(recs)
        assert ps[0].average_sale_price == pytest.approx(250_000.0)

    def test_average_dom(self):
        recs = [
            self._rec("Zeta LLC", dom=30.0),
            self._rec("Zeta LLC", dom=50.0),
        ]
        ps = self._build(recs)
        assert ps[0].average_dom == pytest.approx(40.0)

    def test_linked_properties_count_from_field(self):
        recs = [self._rec("Eta LLC", linked=15)]
        ps = self._build(recs)
        assert ps[0].linked_properties_count == 15
        assert ps[0].properties_owned_count >= 15

    def test_addresses_deduplicated(self):
        recs = [
            self._rec("Theta LLC", addr="123 Main St"),
            self._rec("Theta LLC", addr="123 Main St"),   # duplicate
            self._rec("Theta LLC", addr="456 Oak Ave"),
        ]
        ps = self._build(recs)
        assert len(ps[0].portfolio_addresses) == 2

    def test_zip_codes_active_collected(self):
        recs = [
            self._rec("Iota LLC", zip_="75201"),
            self._rec("Iota LLC", zip_="75202"),
            self._rec("Iota LLC", zip_="75201"),  # dup
        ]
        ps = self._build(recs)
        assert sorted(ps[0].zip_codes_active) == ["75201", "75202"]

    def test_county_active_collected(self):
        recs = [
            self._rec("Kappa LLC", county="Dallas"),
            self._rec("Kappa LLC", county="Collin"),
        ]
        ps = self._build(recs)
        assert "Dallas" in ps[0].counties_active
        assert "Collin" in ps[0].counties_active

    def test_occupancy_mix_counted(self):
        recs = [
            PropertyRecord(
                source_file="t.csv", source_type="portfolio_export",
                owner_name="Lambda LLC", property_address=None,
                city=None, state=None, zip=None, county=None, apn=None,
                estimated_value=None, open_loan_balance=None, equity=None,
                equity_pct=None, ltv=None, last_sale_price=None, last_sale_date=None,
                dom=None, property_type=None, occupancy="owner occupied",
                purchase_method=None, linked_properties_count=None,
            ),
            PropertyRecord(
                source_file="t.csv", source_type="portfolio_export",
                owner_name="Lambda LLC", property_address=None,
                city=None, state=None, zip=None, county=None, apn=None,
                estimated_value=None, open_loan_balance=None, equity=None,
                equity_pct=None, ltv=None, last_sale_price=None, last_sale_date=None,
                dom=None, property_type=None, occupancy="renter",
                purchase_method=None, linked_properties_count=None,
            ),
        ]
        ps = self._build(recs)
        assert ps[0].occupancy_mix.get("owner occupied") == 1
        assert ps[0].occupancy_mix.get("renter") == 1

    def test_source_evidence_populated(self):
        recs = [self._rec("Mu LLC", ev=300_000, sp=290_000)]
        ps = self._build(recs)
        assert ps[0].source_evidence, "source_evidence must not be empty"

    def test_note_supplements_csv_gap(self):
        """When CSV has no estimated_value, note fills it in."""
        recs = [self._rec("Nu LLC", sp=200_000)]  # no estimated_value
        note = ManualNote(
            source_file="note.md", screenshot_paths=[],
            owner_name="Nu LLC", estimated_value=250_000, open_loan_balance=None,
            equity=None, equity_pct=None, last_sale_price=None, last_sale_date=None,
            linked_properties_count=None, county=None, purchase_method=None,
            occupancy=None, raw_text="",
        )
        ps = build_portfolios(recs, [note], {}, {}, ref_date=REF_DATE)
        assert ps[0].total_estimated_value == 250_000.0

    def test_last_purchase_date_from_activity_when_no_csv_dates(self):
        recs = [self._rec("Xi LLC")]  # no sale date
        act = {"xi llc": {
            "buyer_key": "xillc",
            "last_purchase_date": "2026-02-01",
            "recent_purchase_count_90d": 1,
            "acquisition_heat_score": 72.0,
        }}
        ps = build_portfolios(recs, [], {"xillc": act["xi llc"]}, {}, ref_date=REF_DATE)
        xi = next((p for p in ps if "xi" in p.buyer_key), None)
        if xi:
            assert xi.last_purchase_date == "2026-02-01"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Equity normalisation
# ═══════════════════════════════════════════════════════════════════════════════

class TestEquityNormalisation:
    @pytest.mark.parametrize("raw,expected", [
        (72.0,  0.72),
        (0.65,  0.65),
        (100.0, 1.0),
        (1.0,   1.0),
        (0.0,   0.0),
        (None,  None),
    ])
    def test_norm_equity_pct(self, raw, expected):
        result = _norm_equity_pct(raw)
        if expected is None:
            assert result is None
        else:
            assert result == pytest.approx(expected, abs=0.001)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Scoring functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoringConfidence:
    def test_all_signals_present(self):
        score = _score_confidence([300000], [50000], [date(2026, 3, 1)],
                                  [{"source_type": "portfolio_export",
                                    "address": "123 Main"},
                                   {"source_type": "activity_osint"}],
                                  [])
        assert score >= 80.0

    def test_zero_with_no_data(self):
        score = _score_confidence([], [], [], [], [])
        assert score == 0.0

    def test_note_only_penalised(self):
        note = ManualNote(
            source_file="n.md", screenshot_paths=[], owner_name="X LLC",
            estimated_value=None, open_loan_balance=None, equity=None,
            equity_pct=None, last_sale_price=None, last_sale_date=None,
            linked_properties_count=None, county=None, purchase_method=None,
            occupancy=None, raw_text="",
        )
        # No CSV data, only a note → penalty applied
        score_note_only = _score_confidence(
            [], [], [], [{"source_type": "manual_note"}], [note]
        )
        score_csv = _score_confidence(
            [300000], [50000], [date(2026, 3, 1)],
            [{"source_type": "portfolio_export", "address": "X"}], []
        )
        assert score_csv > score_note_only

    def test_capped_at_100(self):
        score = _score_confidence(
            [100000, 200000, 300000],
            [10000, 20000],
            [date(2026, 1, 1), date(2026, 2, 1)],
            [{"source_type": "portfolio_export", "address": "A"},
             {"source_type": "activity_osint"},
             {"source_type": "ownership_graph"}],
            [],
        )
        assert score <= 100.0


class TestScoringLiquidity:
    @pytest.mark.parametrize("ratio,pm,expect_min", [
        (0.95, "cash",  100.0),
        (0.85, "cash",   95.0),
        (0.65, "",       60.0),
        (0.45, "",       40.0),
        (0.25, "",       25.0),
        (0.05, "",        5.0),
        (None, "cash",   25.0),
        (None, "",       20.0),
    ])
    def test_thresholds(self, ratio, pm, expect_min):
        score = _score_liquidity(ratio, pm)
        assert score >= expect_min

    def test_cash_purchase_adds_bonus(self):
        score_cash = _score_liquidity(0.50, "cash")
        score_conv = _score_liquidity(0.50, "conventional")
        assert score_cash > score_conv

    def test_capped_at_100(self):
        assert _score_liquidity(1.0, "cash") <= 100.0


class TestScoringBuyingCapacity:
    def test_large_equity_pool_scores_high(self):
        score = _score_buying_capacity(
            owned_count=20, equity_ratio=0.80,
            total_equity=2_000_000, avg_sale_price=250_000, act={},
        )
        assert score >= 60.0

    def test_zero_portfolio_scores_low(self):
        score = _score_buying_capacity(
            owned_count=0, equity_ratio=None,
            total_equity=None, avg_sale_price=None, act={},
        )
        assert score == 0.0

    def test_multi_purchase_buyer_adds_points(self):
        base = _score_buying_capacity(5, 0.50, 200_000, 200_000, {})
        with_multi = _score_buying_capacity(5, 0.50, 200_000, 200_000,
                                            {"multi_purchase_buyer": True,
                                             "purchase_velocity_score": 0})
        assert with_multi > base

    def test_capped_at_100(self):
        score = _score_buying_capacity(100, 1.0, 50_000_000, 200_000,
                                       {"multi_purchase_buyer": True,
                                        "purchase_velocity_score": 100})
        assert score <= 100.0


class TestScoringLeverageRisk:
    @pytest.mark.parametrize("eq_ratio,expected_approx", [
        (0.0,  100.0),   # fully leveraged
        (0.20,  80.0),
        (0.50,  50.0),
        (0.80,  20.0),
        (1.0,    0.0),   # no loans
    ])
    def test_from_equity_ratio(self, eq_ratio, expected_approx):
        score = _score_leverage_risk(eq_ratio, None, None)
        assert score == pytest.approx(expected_approx, abs=1.0)

    def test_from_value_and_loans(self):
        score = _score_leverage_risk(None, 400_000, 300_000)
        assert score == pytest.approx(75.0, abs=1.0)

    def test_unknown_returns_50(self):
        assert _score_leverage_risk(None, None, None) == 50.0

    def test_capped_at_100(self):
        assert _score_leverage_risk(0.0, 100, 1_000_000) <= 100.0


class TestScoringActivity:
    def test_uses_acquisition_heat_score_directly(self):
        act = {"acquisition_heat_score": 83.5}
        assert _score_activity(act, None, 0) == 83.5

    def test_fallback_recent_days(self):
        score_30d  = _score_activity({}, 25, 0)
        score_180d = _score_activity({}, 160, 0)
        score_old  = _score_activity({}, 730, 0)
        assert score_30d > score_180d > score_old

    def test_fallback_volume_adds_points(self):
        s0 = _score_activity({}, 60, 0)
        s3 = _score_activity({}, 60, 3)
        assert s3 > s0

    def test_no_data_returns_zero(self):
        assert _score_activity({}, None, 0) == 0.0

    def test_capped_at_100(self):
        assert _score_activity({"acquisition_heat_score": 150.0}, 0, 10) <= 100.0


class TestScoringAssetMatch:
    def test_sfr_cash_distress_scores_high(self):
        score = _score_asset_match("SFR Single Family Residential Foreclosure", "Cash")
        assert score >= 75.0

    def test_commercial_only_penalised(self):
        sfr_score  = _score_asset_match("SFR", "Cash")
        comm_score = _score_asset_match("Commercial Office", "Conventional")
        assert sfr_score > comm_score

    def test_land_adds_points(self):
        base = _score_asset_match("", "")
        land = _score_asset_match("Land Lot", "")
        assert land > base

    def test_zero_with_no_signals(self):
        assert _score_asset_match("", "") == 0.0

    def test_capped_at_100(self):
        assert _score_asset_match(
            "SFR Multi-Family Land Distress Foreclosure", "Cash Hard-Money"
        ) <= 100.0


class TestScoringDispoFormula:
    def test_formula_weights(self):
        score = _score_dispo_priority(
            liquidity=100.0, activity=100.0, asset_match=100.0,
            capacity=100.0, confidence=100.0,
        )
        assert score == pytest.approx(100.0, abs=0.1)

    def test_activity_dominates(self):
        high_act = _score_dispo_priority(50, 100, 50, 50, 50)
        low_act  = _score_dispo_priority(50, 0,   50, 50, 50)
        assert high_act > low_act

    def test_zero_inputs_zero(self):
        assert _score_dispo_priority(0, 0, 0, 0, 0) == 0.0

    def test_capped_at_100(self):
        assert _score_dispo_priority(150, 150, 150, 150, 150) <= 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — Portfolio ranking
# ═══════════════════════════════════════════════════════════════════════════════

class TestRanking:
    def _rec(self, owner, ev=None, olb=None, ep=None, sp=None, sd=None, pm=None):
        return PropertyRecord(
            source_file="t.csv", source_type="portfolio_export",
            owner_name=owner, property_address=None, city=None, state=None,
            zip=None, county=None, apn=None,
            estimated_value=ev, open_loan_balance=olb, equity=None,
            equity_pct=ep, ltv=None, last_sale_price=sp, last_sale_date=sd,
            dom=None, property_type=None, occupancy=None,
            purchase_method=pm, linked_properties_count=None,
        )

    def test_recent_active_buyer_ranks_above_dormant_whale(self):
        """1 purchase 15 days ago beats 10 purchases all from 2021."""
        active = self._rec("Active Buyer LLC", sp=200_000, sd="2026-04-24", pm="Cash",
                           ev=500_000, olb=0)
        dormant_recs = [
            self._rec("Dormant Whale LLC", sp=300_000, sd=f"2021-0{i}-01")
            for i in range(1, 10)
        ]
        all_recs = [active] + dormant_recs
        ps = build_portfolios(all_recs, [], {}, {}, ref_date=REF_DATE)

        active_p  = next(p for p in ps if "active" in p.buyer_key)
        dormant_p = next(p for p in ps if "dormant" in p.buyer_key)
        assert active_p.dispo_priority_score > dormant_p.dispo_priority_score

    def test_sorted_descending_by_dispo_priority(self):
        recs = [
            self._rec("Alpha LLC", ev=500_000, ep=0.90, pm="Cash", sd="2026-04-01"),
            self._rec("Beta LLC",  ev=100_000, ep=0.10, pm="Conventional"),
            self._rec("Gamma LLC", ev=300_000, ep=0.60, pm="Cash", sd="2026-02-01"),
        ]
        ps = build_portfolios(recs, [], {}, {}, ref_date=REF_DATE)
        scores = [p.dispo_priority_score for p in ps]
        assert scores == sorted(scores, reverse=True)

    def test_no_fabricated_values_when_no_source(self):
        """Portfolio with no evidence must have None for all financial fields."""
        recs = [self._rec("Unknown LLC")]
        ps = build_portfolios(recs, [], {}, {}, ref_date=REF_DATE)
        p = ps[0]
        assert p.total_estimated_value is None
        assert p.total_open_loan_balance is None
        assert p.total_portfolio_equity is None
        assert p.equity_ratio is None


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — Activity + graph enrichment
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnrichment:
    def _rec(self, owner):
        return PropertyRecord(
            source_file="t.csv", source_type="portfolio_export",
            owner_name=owner, property_address="100 Test St",
            city="Dallas", state="TX", zip="75201", county="Dallas", apn=None,
            estimated_value=None, open_loan_balance=None, equity=None,
            equity_pct=None, ltv=None, last_sale_price=None, last_sale_date=None,
            dom=None, property_type=None, occupancy=None,
            purchase_method=None, linked_properties_count=None,
        )

    def test_activity_heat_score_used(self):
        key = _buyer_key("Atlas Holdings LLC")
        act = {key: {"buyer_key": key, "acquisition_heat_score": 77.0,
                     "recent_purchase_count_90d": 2}}
        recs = [self._rec("Atlas Holdings LLC")]
        ps = build_portfolios(recs, [], act, {}, ref_date=REF_DATE)
        p = next(x for x in ps if x.buyer_key == key)
        assert p.activity_score == pytest.approx(77.0, abs=0.1)

    def test_ownership_graph_adds_property_count(self):
        key = _buyer_key("Bridge Capital LLC")
        graph = {key: {
            "owner_key": key, "display_name": "Bridge Capital LLC",
            "property_count": 8,
            "properties": [{"address": "1 A St", "city": "Dallas", "state": "TX",
                             "zip": "75201", "sale_date": None, "sale_price": None,
                             "deed_type": None, "source_file": "g.csv"}],
            "source_files": ["g.csv"],
        }}
        ps = build_portfolios([], [], {}, graph, ref_date=REF_DATE)
        p = next((x for x in ps if x.buyer_key == key), None)
        assert p is not None
        assert p.properties_owned_count >= 8

    def test_source_evidence_includes_graph_type(self):
        key = _buyer_key("Cedar Fund LLC")
        graph = {key: {
            "owner_key": key, "display_name": "Cedar Fund LLC",
            "property_count": 3,
            "properties": [],
            "source_files": ["deeds.csv"],
        }}
        ps = build_portfolios([], [], {}, graph, ref_date=REF_DATE)
        p = next(x for x in ps if x.buyer_key == key)
        src_types = {e.get("source_type") for e in p.source_evidence}
        assert "ownership_graph" in src_types


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — Output file generation
# ═══════════════════════════════════════════════════════════════════════════════

class TestOutputFiles:
    def _portfolios(self):
        def _p(name, liq, act, asset, cap, conf, er=None, ev=None, lev=50.0):
            d = _score_dispo_priority(liq, act, asset, cap, conf)
            return CashBuyerPortfolio(
                buyer_key=_buyer_key(name), display_name=name,
                buyer_name=None, entity_name=name,
                properties_owned_count=3, linked_properties_count=5,
                total_open_loan_balance=50_000.0 if ev else None,
                total_estimated_value=ev,
                total_portfolio_equity=(ev - 50_000) if ev else None,
                equity_ratio=er,
                average_sale_price=250_000.0, average_dom=30.0,
                purchase_method=["Cash"], counties_active=["Dallas"],
                zip_codes_active=["75201"], property_types_owned=["SFR"],
                occupancy_mix={"owner occupied": 2},
                ownership_length_summary="active ~1.2yr",
                recent_purchase_count=2, last_purchase_date="2026-04-01",
                portfolio_addresses=["123 Main, Dallas, TX 75201"],
                source_evidence=[{"source_type": "portfolio_export",
                                  "source_file": "test.csv",
                                  "address": "123 Main"}],
                confidence_score=conf,
                liquidity_score=liq,
                buying_capacity_score=cap,
                leverage_risk_score=lev,
                activity_score=act,
                asset_match_score=asset,
                dispo_priority_score=d,
            )

        return [
            _p("Alpha LLC",   liq=85, act=90, asset=80, cap=70, conf=90,
               er=0.85, ev=500_000, lev=15.0),
            _p("Beta Corp",   liq=40, act=20, asset=30, cap=20, conf=50,
               lev=70.0),
            _p("Gamma Trust", liq=70, act=60, asset=60, cap=50, conf=75,
               er=0.70, ev=300_000, lev=30.0),
        ]

    def test_all_five_files_written(self, tmp_path):
        write_reports(self._portfolios(), [], tmp_path)
        for fname in [
            "CASH_BUYER_PORTFOLIOS.json",
            "HIGH_CAPACITY_BUYERS.json",
            "LEVERAGED_BUYERS.json",
            "DISPO_TARGETS.md",
            "CASH_BUYER_PORTFOLIO_REPORT.md",
        ]:
            assert (tmp_path / fname).exists(), f"Missing: {fname}"

    def test_cash_buyer_portfolios_json_structure(self, tmp_path):
        write_reports(self._portfolios(), [], tmp_path)
        data = json.loads((tmp_path / "CASH_BUYER_PORTFOLIOS.json").read_text())
        assert "run_timestamp" in data
        assert "portfolio_count" in data
        assert data["portfolio_count"] == 3
        assert isinstance(data["portfolios"], list)
        assert "skipped_files" in data

    def test_portfolio_json_contains_all_required_fields(self, tmp_path):
        write_reports(self._portfolios(), [], tmp_path)
        data = json.loads((tmp_path / "CASH_BUYER_PORTFOLIOS.json").read_text())
        p = data["portfolios"][0]
        required = [
            "buyer_key", "display_name", "properties_owned_count",
            "linked_properties_count", "total_open_loan_balance",
            "total_estimated_value", "total_portfolio_equity", "equity_ratio",
            "average_sale_price", "average_dom", "purchase_method",
            "counties_active", "zip_codes_active", "property_types_owned",
            "occupancy_mix", "ownership_length_summary", "recent_purchase_count",
            "last_purchase_date", "portfolio_addresses", "source_evidence",
            "confidence_score", "liquidity_score", "buying_capacity_score",
            "leverage_risk_score", "activity_score", "asset_match_score",
            "dispo_priority_score",
        ]
        for field in required:
            assert field in p, f"Missing required field: {field}"

    def test_high_capacity_buyers_json_criteria(self, tmp_path):
        write_reports(self._portfolios(), [], tmp_path)
        data = json.loads((tmp_path / "HIGH_CAPACITY_BUYERS.json").read_text())
        for buyer in data["buyers"]:
            assert buyer["liquidity_score"] >= 60.0
            assert buyer["buying_capacity_score"] >= 40.0

    def test_leveraged_buyers_json_criteria(self, tmp_path):
        write_reports(self._portfolios(), [], tmp_path)
        data = json.loads((tmp_path / "LEVERAGED_BUYERS.json").read_text())
        for buyer in data["buyers"]:
            assert buyer["leverage_risk_score"] >= 60.0

    def test_dispo_targets_md_contains_score_table(self, tmp_path):
        write_reports(self._portfolios(), [], tmp_path)
        md = (tmp_path / "DISPO_TARGETS.md").read_text()
        assert "# DISPO_TARGETS" in md
        assert "Dispo Priority Score" in md
        assert "Liquidity Score" in md
        assert "Activity Score" in md

    def test_portfolio_report_md_contains_summary(self, tmp_path):
        write_reports(self._portfolios(), [], tmp_path)
        md = (tmp_path / "CASH_BUYER_PORTFOLIO_REPORT.md").read_text()
        assert "# CASH_BUYER_PORTFOLIO_REPORT" in md
        assert "## Summary" in md
        assert "## Portfolio Detail" in md

    def test_portfolio_report_md_contains_skipped_section(self, tmp_path):
        skipped = [FileResult(path=str(tmp_path / "bad.csv"), skipped=True,
                              skip_reason="could not decode")]
        write_reports(self._portfolios(), skipped, tmp_path)
        md = (tmp_path / "CASH_BUYER_PORTFOLIO_REPORT.md").read_text()
        assert "## Skipped Files" in md
        assert "bad.csv" in md

    def test_portfolios_sorted_by_dispo_score(self, tmp_path):
        write_reports(self._portfolios(), [], tmp_path)
        data = json.loads((tmp_path / "CASH_BUYER_PORTFOLIOS.json").read_text())
        scores = [p["dispo_priority_score"] for p in data["portfolios"]]
        assert scores == sorted(scores, reverse=True)

    def test_empty_portfolios_writes_valid_files(self, tmp_path):
        write_reports([], [], tmp_path)
        for fname in [
            "CASH_BUYER_PORTFOLIOS.json",
            "HIGH_CAPACITY_BUYERS.json",
            "LEVERAGED_BUYERS.json",
            "DISPO_TARGETS.md",
            "CASH_BUYER_PORTFOLIO_REPORT.md",
        ]:
            assert (tmp_path / fname).exists()
        data = json.loads((tmp_path / "CASH_BUYER_PORTFOLIOS.json").read_text())
        assert data["portfolio_count"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — JSON loaders
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoaders:
    def test_load_activity_summary(self, tmp_path):
        payload = {
            "buyer_profiles": [
                {"buyer_key": "alphaholdings", "display_name": "Alpha Holdings",
                 "acquisition_heat_score": 72.5, "recent_purchase_count_90d": 3},
            ]
        }
        (tmp_path / "ACTIVITY_SUMMARY.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        result = load_activity_summary(tmp_path)
        assert "alphaholdings" in result
        assert result["alphaholdings"]["acquisition_heat_score"] == 72.5

    def test_load_activity_summary_missing_file(self, tmp_path):
        result = load_activity_summary(tmp_path / "nonexistent")
        assert result == {}

    def test_load_ownership_graph(self, tmp_path):
        payload = {
            "owners": [
                {"owner_key": "betallc", "display_name": "Beta LLC",
                 "property_count": 5, "properties": [], "source_files": ["d.csv"]},
            ]
        }
        (tmp_path / "OWNERSHIP_GRAPH.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        result = load_ownership_graph(tmp_path)
        assert "betallc" in result
        assert result["betallc"]["property_count"] == 5

    def test_load_ownership_graph_missing_file(self, tmp_path):
        result = load_ownership_graph(tmp_path / "nonexistent")
        assert result == {}

    def test_load_activity_summary_malformed_json(self, tmp_path):
        (tmp_path / "ACTIVITY_SUMMARY.json").write_text("{bad json", encoding="utf-8")
        result = load_activity_summary(tmp_path)
        assert result == {}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — End-to-end pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class TestEndToEnd:
    def test_full_pipeline_propstream_csv(self, tmp_path):
        """CSV with PropStream-style headers produces all 5 output files."""
        raw_dir     = tmp_path / "raw"
        reports_dir = tmp_path / "reports"
        raw_dir.mkdir()

        rows = [
            {"Owner Name": "Oak Street Capital LLC",
             "Property Address": "100 Oak St", "City": "Dallas",
             "State": "TX", "Zip Code": "75201", "County": "Dallas",
             "Estimated Value": "350000", "Open Loan Balance": "0",
             "Equity": "350000", "Equity %": "100",
             "Last Sale Price": "320000", "Last Sale Date": "2026-03-15",
             "Days On Market": "18", "Property Type": "SFR",
             "Occupancy Status": "Tenant Occupied",
             "Purchase Method": "Cash",
             "Linked Properties": "6"},
            {"Owner Name": "Oak Street Capital LLC",
             "Property Address": "200 Elm St", "City": "Dallas",
             "State": "TX", "Zip Code": "75202", "County": "Dallas",
             "Estimated Value": "280000", "Open Loan Balance": "0",
             "Equity": "280000", "Equity %": "100",
             "Last Sale Price": "260000", "Last Sale Date": "2026-01-10",
             "Days On Market": "22", "Property Type": "SFR",
             "Occupancy Status": "Tenant Occupied",
             "Purchase Method": "Cash",
             "Linked Properties": "6"},
        ]
        _write_csv(raw_dir, "propstream_export.csv", rows)

        recs, skipped = ingest_csv_dir(raw_dir)
        portfolios = build_portfolios(recs, [], {}, {}, ref_date=REF_DATE)
        write_reports(portfolios, skipped, reports_dir)

        # All 5 files present
        for fname in [
            "CASH_BUYER_PORTFOLIOS.json",
            "HIGH_CAPACITY_BUYERS.json",
            "LEVERAGED_BUYERS.json",
            "DISPO_TARGETS.md",
            "CASH_BUYER_PORTFOLIO_REPORT.md",
        ]:
            assert (reports_dir / fname).exists(), f"Missing: {fname}"

        # Validate portfolio content
        data = json.loads((reports_dir / "CASH_BUYER_PORTFOLIOS.json").read_text())
        assert data["portfolio_count"] == 1
        p = data["portfolios"][0]
        assert p["display_name"] == "Oak Street Capital LLC"
        assert p["total_estimated_value"] == pytest.approx(630_000.0)
        assert p["equity_ratio"] == pytest.approx(1.0, abs=0.001)
        assert "75201" in p["zip_codes_active"]
        assert "75202" in p["zip_codes_active"]
        assert p["purchase_method"] == ["Cash"]
        assert p["liquidity_score"] >= 90.0
        assert p["leverage_risk_score"] <= 5.0
        assert p["confidence_score"] > 0.0
        assert len(p["source_evidence"]) > 0

        # Should appear in HIGH_CAPACITY_BUYERS due to 100% equity + cash
        hc = json.loads((reports_dir / "HIGH_CAPACITY_BUYERS.json").read_text())
        hc_names = [b["display_name"] for b in hc["buyers"]]
        assert "Oak Street Capital LLC" in hc_names

    def test_full_pipeline_with_note_supplement(self, tmp_path):
        """Note supplements a CSV that has no estimated_value."""
        raw_dir     = tmp_path / "raw"
        notes_dir   = tmp_path / "notes"
        reports_dir = tmp_path / "reports"
        raw_dir.mkdir(); notes_dir.mkdir()

        _write_csv(raw_dir, "export.csv", [
            {"Owner Name": "Pine Ridge LLC",
             "Last Sale Price": "210000",
             "Last Sale Date": "2025-11-01",
             "Purchase Method": "Cash"}
        ])
        (notes_dir / "pine_ridge.md").write_text(
            "owner: Pine Ridge LLC\n"
            "estimated value: $240,000\n"
            "open loan balance: $0\n"
            "screenshot: /screenshots/pine_ridge_propstream.png\n",
            encoding="utf-8",
        )

        recs, _    = ingest_csv_dir(raw_dir)
        notes      = ingest_notes_dir(notes_dir)
        portfolios = build_portfolios(recs, notes, {}, {}, ref_date=REF_DATE)
        write_reports(portfolios, [], reports_dir)

        data = json.loads((reports_dir / "CASH_BUYER_PORTFOLIOS.json").read_text())
        p = data["portfolios"][0]
        assert p["total_estimated_value"] == pytest.approx(240_000.0)
        # Screenshot path must appear in source evidence
        all_screenshots = [
            sc
            for ev in p["source_evidence"]
            for sc in ev.get("screenshot_paths", [])
        ]
        assert any("pine_ridge_propstream.png" in s for s in all_screenshots)
