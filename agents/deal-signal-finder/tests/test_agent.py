"""
Tests for the Deal Signal Finder Agent.

Coverage:
  - SourceType and DealType enums
  - Address / name normalisation helpers
  - Sale-date parsing (multiple formats)
  - Trustee name extraction from raw text
  - Source-type parsing
  - Property grouping (parcel_id vs address vs solo)
  - Signal extraction for each source type
  - Scoring weights and edge cases
  - Routing thresholds
  - Pre-posting detection logic
  - Integration tests for each fixture
  - Cross-record property grouping and signal merging
  - Five output files (content and existence)
  - CLI (dry-run, file input, stdin, error paths)
"""

import json
import sys
import tempfile
import unittest
from datetime import date
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from run import (
    VERIFIED_OPPORTUNITY,
    PROBABLE_OPPORTUNITY,
    WATCH_LIST_THRESHOLD,
    _URGENT_DAYS,
    _UPCOMING_DAYS,
    _WS_TRUSTEE_NOTICE,
    _WS_NOTICE_OF_DEFAULT,
    _WS_SUBSTITUTE_TRUSTEE,
    _WS_SALE_DATE,
    _WS_SALE_URGENT_30D,
    _WS_SALE_UPCOMING_90D,
    _WS_PRE_POSTING,
    _WS_REPEATED_VIOLATIONS,
    _WS_SEVERE_VIOLATION,
    _WS_MUNICIPAL_LIEN,
    _WS_PROPERTY_MAINT,
    _WS_DEMOLITION,
    SourceType,
    DealType,
    DealSignals,
    DealSignalAgent,
    _normalize_address,
    _normalize_name,
    _parse_sale_date,
    _parse_source_type,
    _extract_trustee_from_text,
    _extract_signals,
    _deal_score,
    _route,
    _collect_trustee_entities,
    _PropertyGroup,
    main,
)

# ---------------------------------------------------------------------------
# Constants used across tests
# ---------------------------------------------------------------------------

TODAY = date(2027, 5, 15)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str):
    raw = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    return raw if isinstance(raw, list) else [raw]


TRUSTEE_SALE    = _load("trustee_sale_notice.json")
NOD             = _load("notice_of_default.json")
CODE_VIOLS      = _load("code_violations_batch.json")
DEMOLITION      = _load("demolition_notice.json")
MINIMAL_VIOL    = _load("minimal_violation.json")
FULL_DISTRESS   = _load("full_distress_batch.json")


def _run(records, today=TODAY):
    agent = DealSignalAgent()
    return agent.run(records, today=today)


def _all_profiles(report):
    return (
        report.verified_opportunities
        + report.probable_opportunities
        + report.watch_list
        + report.noise
    )


# ---------------------------------------------------------------------------
# SourceType enum
# ---------------------------------------------------------------------------


class TestSourceType(unittest.TestCase):

    def test_all_ten_values_exist(self):
        expected = {
            "trustee_sale_notice",
            "notice_of_trustee_sale",
            "notice_of_default",
            "pre_foreclosure_list",
            "substitute_trustee_record",
            "auction_calendar",
            "code_violation",
            "nuisance_violation",
            "municipal_lien",
            "demolition_condemnation",
        }
        actual = {st.value for st in SourceType}
        self.assertEqual(actual, expected)

    def test_value_is_string(self):
        self.assertEqual(SourceType.NOTICE_OF_DEFAULT.value, "notice_of_default")

    def test_equality_with_string(self):
        self.assertEqual(SourceType.CODE_VIOLATION, "code_violation")

    def test_used_as_dict_key(self):
        d = {SourceType.MUNICIPAL_LIEN: True}
        self.assertTrue(d[SourceType.MUNICIPAL_LIEN])


# ---------------------------------------------------------------------------
# DealType enum
# ---------------------------------------------------------------------------


class TestDealType(unittest.TestCase):

    def test_four_values_exist(self):
        self.assertEqual(len(DealType), 4)

    def test_verified_value(self):
        self.assertEqual(DealType.VERIFIED_OPPORTUNITY.value, "verified_opportunity")

    def test_noise_value(self):
        self.assertEqual(DealType.NOISE.value, "noise")


# ---------------------------------------------------------------------------
# _normalize_address
# ---------------------------------------------------------------------------


class TestNormalizeAddress(unittest.TestCase):

    def test_lowercases(self):
        self.assertEqual(_normalize_address("742 ELM STREET"), "742 elm street")

    def test_expands_st_abbreviation(self):
        result = _normalize_address("742 Elm St")
        self.assertIn("street", result)
        self.assertNotIn(" st ", result + " ")

    def test_expands_ave_abbreviation(self):
        result = _normalize_address("1204 Oak Ave")
        self.assertIn("avenue", result)

    def test_collapses_whitespace(self):
        result = _normalize_address("742   Elm   Street")
        self.assertNotIn("  ", result)

    def test_strips_punctuation(self):
        result = _normalize_address("900 Market-Place Dr.")
        self.assertNotIn("-", result)

    def test_same_address_different_format_matches(self):
        a = _normalize_address("742 Elm Street, Springfield IL 62701")
        b = _normalize_address("742 Elm St, Springfield IL 62701")
        self.assertEqual(a, b)


# ---------------------------------------------------------------------------
# _parse_sale_date
# ---------------------------------------------------------------------------


class TestParseSaleDate(unittest.TestCase):

    def test_iso_format(self):
        self.assertEqual(_parse_sale_date("2027-06-05"), date(2027, 6, 5))

    def test_us_slash_format(self):
        self.assertEqual(_parse_sale_date("06/05/2027"), date(2027, 6, 5))

    def test_long_month_format(self):
        self.assertEqual(_parse_sale_date("June 5, 2027"), date(2027, 6, 5))

    def test_short_month_format(self):
        self.assertEqual(_parse_sale_date("Jun 5, 2027"), date(2027, 6, 5))

    def test_returns_none_for_garbage(self):
        self.assertIsNone(_parse_sale_date("not a date"))

    def test_returns_none_for_none_input(self):
        self.assertIsNone(_parse_sale_date(None))

    def test_strips_whitespace(self):
        self.assertEqual(_parse_sale_date("  2027-06-05  "), date(2027, 6, 5))


# ---------------------------------------------------------------------------
# _parse_source_type
# ---------------------------------------------------------------------------


class TestParseSourceType(unittest.TestCase):

    def test_valid_lowercase(self):
        self.assertEqual(
            _parse_source_type("notice_of_default"),
            SourceType.NOTICE_OF_DEFAULT,
        )

    def test_valid_mixed_case(self):
        self.assertEqual(
            _parse_source_type("CODE_VIOLATION"),
            SourceType.CODE_VIOLATION,
        )

    def test_invalid_returns_none(self):
        self.assertIsNone(_parse_source_type("unknown_type"))

    def test_none_input_returns_none(self):
        self.assertIsNone(_parse_source_type(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_source_type(""))


# ---------------------------------------------------------------------------
# _extract_trustee_from_text
# ---------------------------------------------------------------------------


class TestExtractTrusteeFromText(unittest.TestCase):

    def test_extracts_trustee_from_colon_pattern(self):
        text = "Trustee: First National Trust Corp\nSale Date: June 1, 2027"
        t, s = _extract_trustee_from_text(text)
        self.assertIsNotNone(t)
        self.assertIn("First National Trust Corp", t)

    def test_extracts_substitute_trustee(self):
        text = "Substitute Trustee: Central Illinois Trustee Services Inc"
        t, s = _extract_trustee_from_text(text)
        self.assertIsNotNone(s)
        self.assertIn("Central Illinois", s)

    def test_substitute_has_priority_over_trustee(self):
        text = (
            "Trustee: Old Trustee Corp\n"
            "Substitute Trustee: New Trustee LLC"
        )
        t, s = _extract_trustee_from_text(text)
        self.assertIsNotNone(s)
        self.assertIn("New Trustee LLC", s)

    def test_as_trustee_pattern(self):
        text = "Midwest Foreclosure Services LLC, as Trustee"
        t, s = _extract_trustee_from_text(text)
        self.assertIsNotNone(t)

    def test_returns_none_for_empty_text(self):
        t, s = _extract_trustee_from_text("")
        self.assertIsNone(t)
        self.assertIsNone(s)

    def test_returns_none_for_unrelated_text(self):
        t, s = _extract_trustee_from_text("Property located at 742 Elm Street.")
        self.assertIsNone(t)
        self.assertIsNone(s)


# ---------------------------------------------------------------------------
# Property grouping
# ---------------------------------------------------------------------------


class TestPropertyGrouping(unittest.TestCase):

    def setUp(self):
        self.agent = DealSignalAgent()

    def test_same_parcel_id_groups_together(self):
        recs = [
            {"record_id": "a", "parcel_id": "11-33-200-010", "source_type": "notice_of_default"},
            {"record_id": "b", "parcel_id": "11-33-200-010", "source_type": "code_violation"},
        ]
        groups = self.agent._group_records(recs)
        self.assertEqual(len(groups), 1)

    def test_different_parcel_ids_create_separate_groups(self):
        recs = [
            {"record_id": "a", "parcel_id": "11-33-200-010", "source_type": "code_violation"},
            {"record_id": "b", "parcel_id": "11-33-200-011", "source_type": "code_violation"},
        ]
        groups = self.agent._group_records(recs)
        self.assertEqual(len(groups), 2)

    def test_same_normalised_address_groups_together(self):
        recs = [
            {"record_id": "a", "address": "742 Elm St, Springfield", "source_type": "code_violation"},
            {"record_id": "b", "address": "742 Elm Street, Springfield", "source_type": "municipal_lien"},
        ]
        groups = self.agent._group_records(recs)
        self.assertEqual(len(groups), 1)

    def test_record_without_parcel_or_address_gets_solo_group(self):
        recs = [{"record_id": "orphan", "source_type": "code_violation"}]
        groups = self.agent._group_records(recs)
        self.assertEqual(len(groups), 1)

    def test_parcel_id_takes_priority_over_address(self):
        recs = [
            {
                "record_id": "a",
                "parcel_id": "11-33-200-010",
                "address": "different address altogether",
                "source_type": "code_violation",
            },
            {
                "record_id": "b",
                "parcel_id": "11-33-200-010",
                "address": "completely different address",
                "source_type": "municipal_lien",
            },
        ]
        groups = self.agent._group_records(recs)
        self.assertEqual(len(groups), 1)


# ---------------------------------------------------------------------------
# _extract_signals unit tests
# ---------------------------------------------------------------------------


def _make_group(records: list[dict]) -> _PropertyGroup:
    agent = DealSignalAgent()
    groups = agent._group_records(records)
    return list(groups.values())[0]


class TestExtractSignalsTrustee(unittest.TestCase):

    def test_notice_of_trustee_sale_sets_flag(self):
        group = _make_group(TRUSTEE_SALE)
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.trustee_notice_present)

    def test_trustee_name_extracted(self):
        group = _make_group(TRUSTEE_SALE)
        sig = _extract_signals(group, TODAY)
        self.assertEqual(sig.trustee_name, "First National Trust Corp")

    def test_trustee_firm_extracted(self):
        group = _make_group(TRUSTEE_SALE)
        sig = _extract_signals(group, TODAY)
        self.assertEqual(sig.trustee_firm, "First National Trust Corp")

    def test_sale_date_parsed(self):
        group = _make_group(TRUSTEE_SALE)
        sig = _extract_signals(group, TODAY)
        self.assertEqual(sig.sale_date, "2027-06-05")

    def test_days_until_sale_computed(self):
        group = _make_group(TRUSTEE_SALE)
        sig = _extract_signals(group, TODAY)
        self.assertEqual(sig.days_until_sale, 21)

    def test_sale_date_present_only_when_future(self):
        rec = dict(TRUSTEE_SALE[0], sale_date="2020-01-01")
        group = _make_group([rec])
        sig = _extract_signals(group, TODAY)
        self.assertFalse(sig.sale_date_present)

    def test_substitute_trustee_sets_flag(self):
        group = _make_group(FULL_DISTRESS)
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.substitute_trustee_present)

    def test_substitute_trustee_name_extracted(self):
        group = _make_group(FULL_DISTRESS)
        sig = _extract_signals(group, TODAY)
        self.assertIsNotNone(sig.substitute_trustee)
        self.assertIn("Central Illinois", sig.substitute_trustee)

    def test_trustee_from_raw_text_fallback(self):
        rec = {
            "record_id": "raw-001",
            "source_type": "notice_of_trustee_sale",
            "parcel_id": "99-01-001-001",
            "raw_text": "Trustee: Fallback Trust Company LLC",
        }
        group = _make_group([rec])
        sig = _extract_signals(group, TODAY)
        self.assertIsNotNone(sig.trustee_name)
        self.assertIn("Fallback Trust Company", sig.trustee_name)

    def test_substitute_trustee_from_raw_text(self):
        rec = {
            "record_id": "raw-002",
            "source_type": "substitute_trustee_record",
            "parcel_id": "99-01-001-002",
            "raw_text": "Substitute Trustee: Raw Text Services Inc",
        }
        group = _make_group([rec])
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.substitute_trustee_present)


class TestExtractSignalsPreForeclosure(unittest.TestCase):

    def test_nod_sets_flag(self):
        group = _make_group(NOD)
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.notice_of_default_present)

    def test_pre_posting_when_nod_without_trustee_notice(self):
        group = _make_group(NOD)
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.pre_posting_signal)

    def test_no_pre_posting_when_trustee_notice_also_present(self):
        # Combine NOD + trustee sale for same property
        records = [
            dict(NOD[0]),
            dict(TRUSTEE_SALE[0], parcel_id=NOD[0]["parcel_id"]),
        ]
        group = _make_group(records)
        sig = _extract_signals(group, TODAY)
        # Has trustee notice → NOT pre-posting
        self.assertFalse(sig.pre_posting_signal)

    def test_pre_foreclosure_list_also_triggers_pre_posting(self):
        rec = {
            "record_id": "pfl-001",
            "source_type": "pre_foreclosure_list",
            "parcel_id": "10-10-010-010",
        }
        group = _make_group([rec])
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.pre_posting_signal)


class TestExtractSignalsViolations(unittest.TestCase):

    def test_violation_count_correct(self):
        group = _make_group(CODE_VIOLS)
        sig = _extract_signals(group, TODAY)
        self.assertEqual(sig.violation_count, 3)

    def test_open_violation_count_correct(self):
        group = _make_group(CODE_VIOLS)
        sig = _extract_signals(group, TODAY)
        self.assertEqual(sig.open_violation_count, 3)

    def test_repeated_violations_set(self):
        group = _make_group(CODE_VIOLS)
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.repeated_code_violations)

    def test_severe_violation_detected(self):
        group = _make_group(CODE_VIOLS)
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.severe_violation_type)
        self.assertIn("structural_deficiency", sig.severe_violation_types)

    def test_maintenance_violation_detected(self):
        group = _make_group(CODE_VIOLS)
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.property_maintenance_signal)

    def test_municipal_lien_from_source_type(self):
        group = _make_group(FULL_DISTRESS)
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.municipal_lien_present)

    def test_municipal_lien_from_field_flag(self):
        rec = {
            "record_id": "ml-001",
            "source_type": "code_violation",  # not municipal_lien source type
            "parcel_id": "10-10-010-020",
            "municipal_lien": True,
        }
        group = _make_group([rec])
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.municipal_lien_present)

    def test_demolition_sets_risk_flag(self):
        group = _make_group(DEMOLITION)
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.demolition_risk)

    def test_demolition_sets_severe_flag(self):
        group = _make_group(DEMOLITION)
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.severe_violation_type)

    def test_single_non_severe_open_violation_no_repeated(self):
        group = _make_group(MINIMAL_VIOL)
        sig = _extract_signals(group, TODAY)
        self.assertFalse(sig.repeated_code_violations)
        self.assertFalse(sig.severe_violation_type)

    def test_two_open_violations_not_repeated_without_total_threshold(self):
        recs = [
            {"record_id": "x1", "source_type": "code_violation", "parcel_id": "99-99-99-001",
             "violation_type": "graffiti", "violation_status": "open"},
            {"record_id": "x2", "source_type": "code_violation", "parcel_id": "99-99-99-001",
             "violation_type": "exterior_maintenance", "violation_status": "open"},
        ]
        group = _make_group(recs)
        sig = _extract_signals(group, TODAY)
        # 2 open < 3 open AND total < 3 → NOT repeated
        self.assertFalse(sig.repeated_code_violations)

    def test_two_open_plus_one_resolved_triggers_repeated(self):
        recs = [
            {"record_id": "y1", "source_type": "code_violation", "parcel_id": "99-99-99-002",
             "violation_type": "graffiti", "violation_status": "open"},
            {"record_id": "y2", "source_type": "code_violation", "parcel_id": "99-99-99-002",
             "violation_type": "exterior_maintenance", "violation_status": "open"},
            {"record_id": "y3", "source_type": "code_violation", "parcel_id": "99-99-99-002",
             "violation_type": "debris_accumulation", "violation_status": "resolved"},
        ]
        group = _make_group(recs)
        sig = _extract_signals(group, TODAY)
        # total=3 AND open=2 → repeated
        self.assertTrue(sig.repeated_code_violations)

    def test_source_evidence_populated(self):
        group = _make_group(FULL_DISTRESS)
        sig = _extract_signals(group, TODAY)
        self.assertTrue(sig.source_evidence)


# ---------------------------------------------------------------------------
# _deal_score unit tests
# ---------------------------------------------------------------------------


class TestDealScore(unittest.TestCase):

    def _score(self, **kwargs) -> float:
        sig = DealSignals(**kwargs)
        return _deal_score(sig)

    def test_zero_with_no_signals(self):
        self.assertEqual(self._score(), 0.0)

    def test_trustee_notice_weight(self):
        self.assertAlmostEqual(
            self._score(trustee_notice_present=True),
            _WS_TRUSTEE_NOTICE,
            places=4,
        )

    def test_nod_weight(self):
        self.assertAlmostEqual(
            self._score(notice_of_default_present=True),
            _WS_NOTICE_OF_DEFAULT,
            places=4,
        )

    def test_substitute_trustee_weight(self):
        self.assertAlmostEqual(
            self._score(substitute_trustee_present=True),
            _WS_SUBSTITUTE_TRUSTEE,
            places=4,
        )

    def test_sale_date_with_urgent_adds_both_weights(self):
        score = self._score(
            trustee_notice_present=True,
            sale_date_present=True,
            days_until_sale=10,
        )
        expected = _WS_TRUSTEE_NOTICE + _WS_SALE_DATE + _WS_SALE_URGENT_30D
        self.assertAlmostEqual(score, expected, places=4)

    def test_sale_date_upcoming_range(self):
        score = self._score(sale_date_present=True, days_until_sale=60)
        expected = _WS_SALE_DATE + _WS_SALE_UPCOMING_90D
        self.assertAlmostEqual(score, expected, places=4)

    def test_sale_date_beyond_90d_no_urgency_bonus(self):
        score = self._score(sale_date_present=True, days_until_sale=120)
        self.assertAlmostEqual(score, _WS_SALE_DATE, places=4)

    def test_sale_date_not_present_no_urgency_even_if_days_known(self):
        # sale_date_present=False means sale already passed
        score = self._score(sale_date_present=False, days_until_sale=10)
        self.assertEqual(score, 0.0)

    def test_pre_posting_weight(self):
        self.assertAlmostEqual(
            self._score(pre_posting_signal=True),
            _WS_PRE_POSTING,
            places=4,
        )

    def test_repeated_violations_weight(self):
        self.assertAlmostEqual(
            self._score(repeated_code_violations=True),
            _WS_REPEATED_VIOLATIONS,
            places=4,
        )

    def test_all_violation_signals_additive(self):
        score = self._score(
            repeated_code_violations=True,
            severe_violation_type=True,
            municipal_lien_present=True,
            property_maintenance_signal=True,
            demolition_risk=True,
        )
        expected = (
            _WS_REPEATED_VIOLATIONS + _WS_SEVERE_VIOLATION
            + _WS_MUNICIPAL_LIEN + _WS_PROPERTY_MAINT + _WS_DEMOLITION
        )
        self.assertAlmostEqual(score, expected, places=4)

    def test_score_capped_at_one(self):
        score = self._score(
            trustee_notice_present=True,
            notice_of_default_present=True,
            substitute_trustee_present=True,
            pre_posting_signal=True,
            sale_date_present=True,
            days_until_sale=5,
            repeated_code_violations=True,
            severe_violation_type=True,
            municipal_lien_present=True,
            property_maintenance_signal=True,
            demolition_risk=True,
        )
        self.assertLessEqual(score, 1.0)

    def test_score_floor_at_zero(self):
        self.assertGreaterEqual(_deal_score(DealSignals()), 0.0)


# ---------------------------------------------------------------------------
# _route
# ---------------------------------------------------------------------------


class TestRoute(unittest.TestCase):

    def test_verified_opportunity_at_threshold(self):
        self.assertEqual(_route(VERIFIED_OPPORTUNITY), DealType.VERIFIED_OPPORTUNITY)

    def test_probable_opportunity_at_threshold(self):
        self.assertEqual(_route(PROBABLE_OPPORTUNITY), DealType.PROBABLE_OPPORTUNITY)

    def test_watch_list_at_threshold(self):
        self.assertEqual(_route(WATCH_LIST_THRESHOLD), DealType.WATCH_LIST)

    def test_noise_below_watch_list(self):
        self.assertEqual(_route(WATCH_LIST_THRESHOLD - 0.001), DealType.NOISE)

    def test_zero_is_noise(self):
        self.assertEqual(_route(0.0), DealType.NOISE)

    def test_boundary_between_probable_and_watch(self):
        just_above = PROBABLE_OPPORTUNITY + 0.001
        just_below = PROBABLE_OPPORTUNITY - 0.001
        self.assertEqual(_route(just_above), DealType.PROBABLE_OPPORTUNITY)
        self.assertEqual(_route(just_below), DealType.WATCH_LIST)


# ---------------------------------------------------------------------------
# Trustee entity collection
# ---------------------------------------------------------------------------


class TestCollectTrusteeEntities(unittest.TestCase):

    def _profile(self, trustee_name=None, trustee_firm=None, parcel_id=None,
                 substitute_trustee=None, sale_date=None):
        from run import DealProfile
        sig = DealSignals(
            trustee_name=trustee_name,
            trustee_firm=trustee_firm,
            substitute_trustee=substitute_trustee,
            sale_date=sale_date,
            substitute_trustee_present=bool(substitute_trustee),
            source_evidence=[],
        )
        return DealProfile(
            property_key=parcel_id or "k",
            parcel_id=parcel_id,
            address=None,
            owner_name=None,
            deal_type=DealType.WATCH_LIST,
            deal_score=0.2,
            signals=sig,
            evidence_flags=[],
            source_records=[],
            source_types=[],
        )

    def test_empty_profiles_returns_empty(self):
        self.assertEqual(_collect_trustee_entities([]), [])

    def test_single_entity_captured(self):
        p = self._profile(trustee_firm="Test Trust LLC", parcel_id="11-11-111-001")
        result = _collect_trustee_entities([p])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["trustee_firm"], "Test Trust LLC")

    def test_same_firm_two_properties_merged(self):
        p1 = self._profile(trustee_firm="Big Trust LLC", parcel_id="p-001")
        p2 = self._profile(trustee_firm="Big Trust LLC", parcel_id="p-002")
        result = _collect_trustee_entities([p1, p2])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["property_count"], 2)

    def test_different_firms_produce_separate_entries(self):
        p1 = self._profile(trustee_firm="Alpha Trust LLC", parcel_id="p-001")
        p2 = self._profile(trustee_firm="Beta Trust Corp", parcel_id="p-002")
        result = _collect_trustee_entities([p1, p2])
        self.assertEqual(len(result), 2)

    def test_sorted_by_property_count_descending(self):
        p1 = self._profile(trustee_firm="Small Trust", parcel_id="p-001")
        p2 = self._profile(trustee_firm="Big Trust", parcel_id="p-002")
        p3 = self._profile(trustee_firm="Big Trust", parcel_id="p-003")
        result = _collect_trustee_entities([p1, p2, p3])
        self.assertEqual(result[0]["trustee_firm"], "Big Trust")

    def test_earliest_sale_date_computed(self):
        p1 = self._profile(trustee_firm="T", parcel_id="p-001", sale_date="2027-07-01")
        p2 = self._profile(trustee_firm="T", parcel_id="p-002", sale_date="2027-06-15")
        result = _collect_trustee_entities([p1, p2])
        self.assertEqual(result[0]["earliest_sale"], "2027-06-15")


# ---------------------------------------------------------------------------
# Integration: trustee sale notice → PROBABLE_OPPORTUNITY
# ---------------------------------------------------------------------------


class TestTrusteeSaleIntegration(unittest.TestCase):

    def setUp(self):
        self.report = _run(TRUSTEE_SALE)

    def test_classified_as_probable_opportunity(self):
        self.assertEqual(len(self.report.probable_opportunities), 1)
        self.assertEqual(len(self.report.verified_opportunities), 0)

    def test_deal_score(self):
        p = self.report.probable_opportunities[0]
        self.assertAlmostEqual(p.deal_score, 0.46, places=4)

    def test_trustee_notice_present(self):
        p = self.report.probable_opportunities[0]
        self.assertTrue(p.signals.trustee_notice_present)

    def test_trustee_name_preserved(self):
        p = self.report.probable_opportunities[0]
        self.assertEqual(p.signals.trustee_name, "First National Trust Corp")

    def test_sale_date_preserved(self):
        p = self.report.probable_opportunities[0]
        self.assertEqual(p.signals.sale_date, "2027-06-05")

    def test_days_until_sale_21(self):
        p = self.report.probable_opportunities[0]
        self.assertEqual(p.signals.days_until_sale, 21)

    def test_sale_date_present_true(self):
        p = self.report.probable_opportunities[0]
        self.assertTrue(p.signals.sale_date_present)

    def test_no_pre_posting(self):
        p = self.report.probable_opportunities[0]
        self.assertFalse(p.signals.pre_posting_signal)

    def test_evidence_flags_populated(self):
        p = self.report.probable_opportunities[0]
        self.assertTrue(p.evidence_flags)

    def test_total_properties_one(self):
        self.assertEqual(self.report.total_properties, 1)


# ---------------------------------------------------------------------------
# Integration: notice of default → WATCH_LIST (pre-posting)
# ---------------------------------------------------------------------------


class TestNoticeOfDefaultIntegration(unittest.TestCase):

    def setUp(self):
        self.report = _run(NOD)

    def test_classified_as_watch_list(self):
        self.assertEqual(len(self.report.watch_list), 1)

    def test_deal_score(self):
        p = self.report.watch_list[0]
        self.assertAlmostEqual(p.deal_score, 0.23, places=4)

    def test_notice_of_default_flag(self):
        p = self.report.watch_list[0]
        self.assertTrue(p.signals.notice_of_default_present)

    def test_pre_posting_flag(self):
        p = self.report.watch_list[0]
        self.assertTrue(p.signals.pre_posting_signal)

    def test_no_sale_date(self):
        p = self.report.watch_list[0]
        self.assertIsNone(p.signals.sale_date)

    def test_owner_preserved(self):
        p = self.report.watch_list[0]
        self.assertEqual(p.owner_name, "Cheryl Bowman")


# ---------------------------------------------------------------------------
# Integration: code violations batch → WATCH_LIST
# ---------------------------------------------------------------------------


class TestCodeViolationsIntegration(unittest.TestCase):

    def setUp(self):
        self.report = _run(CODE_VIOLS)

    def test_classified_as_watch_list(self):
        self.assertEqual(len(self.report.watch_list), 1)

    def test_deal_score(self):
        p = self.report.watch_list[0]
        self.assertAlmostEqual(p.deal_score, 0.27, places=4)

    def test_violation_count(self):
        p = self.report.watch_list[0]
        self.assertEqual(p.signals.violation_count, 3)

    def test_repeated_violations(self):
        p = self.report.watch_list[0]
        self.assertTrue(p.signals.repeated_code_violations)

    def test_severe_violation(self):
        p = self.report.watch_list[0]
        self.assertTrue(p.signals.severe_violation_type)

    def test_maintenance_signal(self):
        p = self.report.watch_list[0]
        self.assertTrue(p.signals.property_maintenance_signal)

    def test_all_three_records_in_one_group(self):
        self.assertEqual(self.report.total_properties, 1)
        self.assertEqual(self.report.total_records, 3)


# ---------------------------------------------------------------------------
# Integration: demolition notice → WATCH_LIST
# ---------------------------------------------------------------------------


class TestDemolitionIntegration(unittest.TestCase):

    def setUp(self):
        self.report = _run(DEMOLITION)

    def test_classified_as_watch_list(self):
        self.assertEqual(len(self.report.watch_list), 1)

    def test_deal_score(self):
        p = self.report.watch_list[0]
        self.assertAlmostEqual(p.deal_score, 0.22, places=4)

    def test_demolition_risk_flag(self):
        p = self.report.watch_list[0]
        self.assertTrue(p.signals.demolition_risk)

    def test_severe_violation_flag(self):
        p = self.report.watch_list[0]
        self.assertTrue(p.signals.severe_violation_type)

    def test_condemnation_in_severe_types(self):
        p = self.report.watch_list[0]
        self.assertIn("condemnation", p.signals.severe_violation_types)


# ---------------------------------------------------------------------------
# Integration: minimal violation → NOISE
# ---------------------------------------------------------------------------


class TestMinimalViolationIntegration(unittest.TestCase):

    def setUp(self):
        self.report = _run(MINIMAL_VIOL)

    def test_classified_as_noise(self):
        self.assertEqual(len(self.report.noise), 1)

    def test_deal_score(self):
        p = self.report.noise[0]
        self.assertAlmostEqual(p.deal_score, 0.05, places=4)

    def test_only_maintenance_signal(self):
        p = self.report.noise[0]
        self.assertTrue(p.signals.property_maintenance_signal)
        self.assertFalse(p.signals.severe_violation_type)
        self.assertFalse(p.signals.repeated_code_violations)
        self.assertFalse(p.signals.trustee_notice_present)


# ---------------------------------------------------------------------------
# Integration: full distress batch → VERIFIED_OPPORTUNITY
# ---------------------------------------------------------------------------


class TestFullDistressIntegration(unittest.TestCase):

    def setUp(self):
        self.report = _run(FULL_DISTRESS)

    def test_classified_as_verified_opportunity(self):
        self.assertEqual(len(self.report.verified_opportunities), 1)

    def test_deal_score(self):
        p = self.report.verified_opportunities[0]
        self.assertAlmostEqual(p.deal_score, 0.77, places=4)

    def test_all_five_records_in_one_property(self):
        self.assertEqual(self.report.total_records, 5)
        self.assertEqual(self.report.total_properties, 1)

    def test_trustee_notice_present(self):
        p = self.report.verified_opportunities[0]
        self.assertTrue(p.signals.trustee_notice_present)

    def test_substitute_trustee_present(self):
        p = self.report.verified_opportunities[0]
        self.assertTrue(p.signals.substitute_trustee_present)
        self.assertIsNotNone(p.signals.substitute_trustee)

    def test_sale_date_urgent(self):
        p = self.report.verified_opportunities[0]
        self.assertTrue(p.signals.sale_date_present)
        self.assertLessEqual(p.signals.days_until_sale, _URGENT_DAYS)

    def test_severe_violation(self):
        p = self.report.verified_opportunities[0]
        self.assertTrue(p.signals.severe_violation_type)

    def test_municipal_lien(self):
        p = self.report.verified_opportunities[0]
        self.assertTrue(p.signals.municipal_lien_present)

    def test_property_maintenance_signal(self):
        p = self.report.verified_opportunities[0]
        self.assertTrue(p.signals.property_maintenance_signal)

    def test_source_types_cover_all_present_sources(self):
        p = self.report.verified_opportunities[0]
        self.assertIn("notice_of_trustee_sale", p.source_types)
        self.assertIn("substitute_trustee_record", p.source_types)
        self.assertIn("code_violation", p.source_types)
        self.assertIn("municipal_lien", p.source_types)

    def test_distress_signal_confidence_matches_score(self):
        p = self.report.verified_opportunities[0]
        self.assertAlmostEqual(
            p.signals.distress_signal_confidence, p.deal_score, places=4
        )


# ---------------------------------------------------------------------------
# Cross-record grouping and signal merging
# ---------------------------------------------------------------------------


class TestCrossRecordMerging(unittest.TestCase):

    def test_nod_plus_trustee_sale_same_parcel(self):
        records = [
            dict(NOD[0]),
            dict(TRUSTEE_SALE[0], parcel_id=NOD[0]["parcel_id"]),
        ]
        report = _run(records)
        self.assertEqual(report.total_properties, 1)
        p = _all_profiles(report)[0]
        self.assertTrue(p.signals.notice_of_default_present)
        self.assertTrue(p.signals.trustee_notice_present)
        # NOD + trustee notice → NOT pre-posting
        self.assertFalse(p.signals.pre_posting_signal)

    def test_violation_plus_nod_creates_violation_match_candidate(self):
        records = [
            dict(NOD[0]),
            dict(CODE_VIOLS[0], parcel_id=NOD[0]["parcel_id"]),
        ]
        report = _run(records)
        p = _all_profiles(report)[0]
        self.assertTrue(p.signals.notice_of_default_present)
        self.assertGreater(p.signals.violation_count, 0)

    def test_separate_parcel_ids_remain_separate(self):
        report = _run(TRUSTEE_SALE + NOD)
        self.assertEqual(report.total_properties, 2)

    def test_reports_sorted_by_score_descending(self):
        report = _run(TRUSTEE_SALE + MINIMAL_VIOL)
        all_p = _all_profiles(report)
        scores = [p.deal_score for p in all_p]
        self.assertEqual(scores, sorted(scores, reverse=True))


# ---------------------------------------------------------------------------
# Output file generation
# ---------------------------------------------------------------------------


class TestOutputGeneration(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.agent = DealSignalAgent(reports_dir=self.tmp)

    def test_all_five_files_created(self):
        report = self.agent.run(FULL_DISTRESS, today=TODAY)
        self.agent.write_outputs(report)
        expected = [
            "TRUSTEE_SIGNAL_REPORT.md",
            "CODE_VIOLATION_REPORT.md",
            "TRUSTEE_ENTITIES.json",
            "PRE_FORECLOSURE_SIGNALS.json",
            "VIOLATION_MATCHES.json",
        ]
        for fname in expected:
            self.assertTrue((self.tmp / fname).exists(), f"Missing: {fname}")

    def test_trustee_signal_report_contains_trustee_name(self):
        report = self.agent.run(TRUSTEE_SALE, today=TODAY)
        self.agent.write_outputs(report)
        content = (self.tmp / "TRUSTEE_SIGNAL_REPORT.md").read_text()
        self.assertIn("First National Trust Corp", content)

    def test_trustee_signal_report_contains_sale_date(self):
        report = self.agent.run(TRUSTEE_SALE, today=TODAY)
        self.agent.write_outputs(report)
        content = (self.tmp / "TRUSTEE_SIGNAL_REPORT.md").read_text()
        self.assertIn("2027-06-05", content)

    def test_trustee_signal_report_marks_urgent(self):
        report = self.agent.run(FULL_DISTRESS, today=TODAY)
        self.agent.write_outputs(report)
        content = (self.tmp / "TRUSTEE_SIGNAL_REPORT.md").read_text()
        self.assertIn("URGENT", content)

    def test_code_violation_report_mentions_severe(self):
        report = self.agent.run(CODE_VIOLS, today=TODAY)
        self.agent.write_outputs(report)
        content = (self.tmp / "CODE_VIOLATION_REPORT.md").read_text()
        self.assertIn("structural_deficiency", content)

    def test_code_violation_report_mentions_repeated(self):
        report = self.agent.run(CODE_VIOLS, today=TODAY)
        self.agent.write_outputs(report)
        content = (self.tmp / "CODE_VIOLATION_REPORT.md").read_text()
        self.assertIn("Repeated", content)

    def test_trustee_entities_json_valid(self):
        report = self.agent.run(FULL_DISTRESS, today=TODAY)
        self.agent.write_outputs(report)
        data = json.loads((self.tmp / "TRUSTEE_ENTITIES.json").read_text())
        self.assertIn("entities", data)
        self.assertIsInstance(data["entities"], list)

    def test_trustee_entities_contains_firm_name(self):
        report = self.agent.run(FULL_DISTRESS, today=TODAY)
        self.agent.write_outputs(report)
        data = json.loads((self.tmp / "TRUSTEE_ENTITIES.json").read_text())
        firm_names = [e.get("trustee_firm") for e in data["entities"]]
        self.assertIn("Midwest Foreclosure Services LLC", firm_names)

    def test_pre_foreclosure_signals_json_valid(self):
        report = self.agent.run(NOD, today=TODAY)
        self.agent.write_outputs(report)
        data = json.loads((self.tmp / "PRE_FORECLOSURE_SIGNALS.json").read_text())
        self.assertIn("signals", data)
        self.assertGreater(data["pre_foreclosure_count"], 0)

    def test_pre_foreclosure_signals_empty_when_no_nod(self):
        report = self.agent.run(MINIMAL_VIOL, today=TODAY)
        self.agent.write_outputs(report)
        data = json.loads((self.tmp / "PRE_FORECLOSURE_SIGNALS.json").read_text())
        self.assertEqual(data["pre_foreclosure_count"], 0)

    def test_violation_matches_json_valid(self):
        # Combine NOD + code violation for same property = violation match
        records = [
            dict(NOD[0]),
            dict(CODE_VIOLS[0], parcel_id=NOD[0]["parcel_id"]),
        ]
        report = self.agent.run(records, today=TODAY)
        self.agent.write_outputs(report)
        data = json.loads((self.tmp / "VIOLATION_MATCHES.json").read_text())
        self.assertIn("matches", data)

    def test_violation_matches_empty_when_no_overlap(self):
        # Trustee sale only (no violations) → no violation match
        report = self.agent.run(TRUSTEE_SALE, today=TODAY)
        self.agent.write_outputs(report)
        data = json.loads((self.tmp / "VIOLATION_MATCHES.json").read_text())
        self.assertEqual(data["match_count"], 0)

    def test_trustee_signal_report_no_signals_message(self):
        report = self.agent.run(MINIMAL_VIOL, today=TODAY)
        self.agent.write_outputs(report)
        content = (self.tmp / "TRUSTEE_SIGNAL_REPORT.md").read_text()
        self.assertIn("No trustee", content)

    def test_code_violation_report_no_violations_message(self):
        report = self.agent.run(TRUSTEE_SALE, today=TODAY)
        self.agent.write_outputs(report)
        content = (self.tmp / "CODE_VIOLATION_REPORT.md").read_text()
        self.assertIn("No violation", content)

    def test_today_preserved_in_report_json(self):
        report = self.agent.run(TRUSTEE_SALE, today=TODAY)
        self.agent.write_outputs(report)
        data = json.loads((self.tmp / "TRUSTEE_ENTITIES.json").read_text())
        self.assertEqual(data["today"], "2027-05-15")


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI(unittest.TestCase):

    def test_dry_run_from_stdin_trustee(self):
        payload = json.dumps(TRUSTEE_SALE)
        with patch("sys.stdin", StringIO(payload)):
            with patch("sys.stdout", new_callable=StringIO) as out:
                code = main(["--dry-run", "--today", "2027-05-15"])
        self.assertEqual(code, 0)
        self.assertIn("Probable", out.getvalue())

    def test_dry_run_single_dict_stdin(self):
        payload = json.dumps(TRUSTEE_SALE[0])
        with patch("sys.stdin", StringIO(payload)):
            with patch("sys.stdout", new_callable=StringIO):
                code = main(["--dry-run", "--today", "2027-05-15"])
        self.assertEqual(code, 0)

    def test_nonexistent_path_returns_one(self):
        code = main(["/nonexistent/does_not_exist.json"])
        self.assertEqual(code, 1)

    def test_bad_stdin_json_returns_one(self):
        with patch("sys.stdin", StringIO("not { json }")):
            code = main(["--dry-run"])
        self.assertEqual(code, 1)

    def test_noise_only_returns_nonzero(self):
        payload = json.dumps(MINIMAL_VIOL)
        with patch("sys.stdin", StringIO(payload)):
            with patch("sys.stdout", new_callable=StringIO):
                code = main(["--dry-run"])
        self.assertEqual(code, 1)

    def test_empty_batch_returns_zero(self):
        payload = json.dumps([])
        with patch("sys.stdin", StringIO(payload)):
            with patch("sys.stdout", new_callable=StringIO):
                code = main(["--dry-run"])
        self.assertEqual(code, 0)

    def test_load_from_file(self):
        import os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(TRUSTEE_SALE, f)
            fname = f.name
        try:
            with patch("sys.stdout", new_callable=StringIO):
                code = main(["--dry-run", "--today", "2027-05-15", fname])
            self.assertEqual(code, 0)
        finally:
            os.unlink(fname)

    def test_invalid_today_flag_returns_one(self):
        payload = json.dumps(TRUSTEE_SALE)
        with patch("sys.stdin", StringIO(payload)):
            code = main(["--dry-run", "--today", "not-a-date"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
