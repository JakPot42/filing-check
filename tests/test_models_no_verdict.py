"""Structural guardrail for models.py -- a field-scan plus decision-module purity check.

Fails loudly if a future edit ever adds a field that could hold a verdict about a filer,
attaches a rate or score to a company, lets an amendment enter the cross-source findings, or
lets a match rate exist without its interpretation.

Proven green BEFORE any reconciliation logic exists. This is the project's legitimacy: it
names real companies against real government records, so "it cannot represent an accusation"
has to be a property of the code, not a promise in a README.
"""
from __future__ import annotations

import dataclasses
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models import (
    AmendmentObservation,
    FieldDifference,
    FilingRecord,
    Finding,
    FindingKind,
    IndependentRecord,
    Match,
    MatchRateDisclosure,
    ReconciliationReport,
    SourceRef,
)

ALL_MODELS = [SourceRef, FilingRecord, IndependentRecord, Match, FieldDifference, Finding,
              AmendmentObservation, MatchRateDisclosure, ReconciliationReport]

# A -- roots that may never name a field on ANY model: a verdict, an intent, or a duty breach
_FORBIDDEN_ROOTS = [
    "conceal", "coverup", "cover_up", "suppress", "withheld", "withhold", "hidden",
    "omission", "omitted", "underreport", "under_report", "misreport", "mis_report",
    "intent", "deliberate", "willful", "wilful", "knowing", "motive",
    "negligen", "reckless", "culpab", "blame", "fault", "guilt", "liab",
    "wrongdoing", "misconduct", "fraud", "dishonest", "deceit", "deceptive",
    "violation", "violat", "noncompliance", "non_compliance", "breach",
    "verdict", "accusation", "allegation_of", "penalty", "sanction", "enforcement",
]

# B -- no score/rank/grade on the models that describe a difference, a run, or the report.
# Match.match_score is the deliberate exception: it scores a RECORD PAIR, not a company.
_NO_SCORE_MODELS = [Finding, FieldDifference, AmendmentObservation, MatchRateDisclosure,
                    ReconciliationReport]
_FORBIDDEN_SCORE_ROOTS = ["score", "rating", "grade", "rank", "index", "aggregate",
                          "overall", "severity", "tier", "risk_level"]

# C -- the match rate may never be attached to a company
_ENTITY_ROOTS = ["reporting_entity", "entity", "company", "filer", "operator",
                 "manufacturer", "make", "brand"]


def test_A_no_verdict_or_intent_field_on_any_model():
    for model in ALL_MODELS:
        for f in dataclasses.fields(model):
            for root in _FORBIDDEN_ROOTS:
                assert root not in f.name.lower(), (
                    f"{model.__name__}.{f.name} contains {root!r} -- no model may store a "
                    f"verdict, an intent, or a duty-breach claim about a filer."
                )


def test_B_no_score_on_finding_amendment_coverage_or_report():
    for model in _NO_SCORE_MODELS:
        for f in dataclasses.fields(model):
            for root in _FORBIDDEN_SCORE_ROOTS:
                assert root not in f.name.lower(), (
                    f"{model.__name__}.{f.name} contains {root!r} -- differences are not "
                    f"graded and companies are not scored."
                )


def test_B2_match_score_exists_only_on_match_and_is_a_record_pair_score():
    # Its location is deliberate, not incidental: it scores the linkage between two documents.
    match_fields = {f.name for f in dataclasses.fields(Match)}
    assert "match_score" in match_fields
    assert "match_confidence" in match_fields
    # ...and it is not reachable from any model that describes a company's behaviour.
    for model in _NO_SCORE_MODELS:
        assert "match_score" not in {f.name for f in dataclasses.fields(model)}


def test_C_match_rate_is_never_attached_to_a_company():
    """THE structural expression of the no-per-company-rate decision (models.py guarantee 2).

    A per-company rate reads as 'this company is missing N% of its incidents'. It is not that
    -- it is dominated by whether the fleet is consumer-owned, by fleet size, and by
    geography. There is nowhere on this object to put a company, so the code cannot produce
    one without a visible, deliberate model change that trips this test."""
    for f in dataclasses.fields(MatchRateDisclosure):
        for root in _ENTITY_ROOTS:
            assert root not in f.name.lower(), (
                f"MatchRateDisclosure.{f.name} names {root!r} -- the match rate describes a "
                f"reconciliation run and this tool's method, never a company."
            )


def test_D_report_exposes_no_numeric_field():
    for f in dataclasses.fields(ReconciliationReport):
        assert f.type not in ("int", "float", "int | None", "float | None"), (
            f"ReconciliationReport.{f.name} is numeric ({f.type}) -- counts belong on the "
            f"coverage object, which carries its own interpretation."
        )


def test_E_amendment_is_a_separate_type_and_cannot_be_a_finding():
    """An amendment compares a filing against a later version of ITSELF. Keeping it a
    different type is what stops it entering the cross-source findings or the match rate."""
    assert not issubclass(AmendmentObservation, Finding)
    assert "AMENDMENT" not in FindingKind.ALL
    assert FindingKind.ALL == (FindingKind.UNMATCHED_INDEPENDENT_RECORD,
                               FindingKind.FIELD_DIFFERENCE)
    # No FindingKind names concealment, omission, or a failure to report.
    for kind in FindingKind.ALL:
        for root in ("CONCEAL", "OMIT", "OMISSION", "FAIL", "UNDERREPORT", "VIOLAT", "MISSING"):
            assert root not in kind.upper(), f"FindingKind {kind!r} contains {root!r}"


def test_E2_report_findings_and_amendments_are_distinct_collections():
    fields = {f.name for f in dataclasses.fields(ReconciliationReport)}
    assert "findings" in fields and "amendments" in fields, (
        "amendments must have their own collection -- merging them into findings would put a "
        "self-comparison into the cross-source match rate"
    )


def test_F_match_rate_cannot_exist_without_its_interpretation():
    with pytest.raises(ValueError):
        MatchRateDisclosure(independent_records_examined=100, independent_records_matched=12,
                            scope_note="s", method_note="m", interpretation="")
    with pytest.raises(ValueError):
        MatchRateDisclosure(independent_records_examined=100, independent_records_matched=12,
                            scope_note="s", method_note="m", interpretation="   ")


def test_F2_match_rate_arithmetic_is_guarded():
    with pytest.raises(ValueError):
        MatchRateDisclosure(independent_records_examined=10, independent_records_matched=11,
                            scope_note="s", method_note="m", interpretation="i")
    with pytest.raises(ValueError):
        MatchRateDisclosure(independent_records_examined=-1, independent_records_matched=0,
                            scope_note="s", method_note="m", interpretation="i")


def test_F3_empty_population_yields_no_rate_rather_than_a_fake_one():
    d = MatchRateDisclosure(independent_records_examined=0, independent_records_matched=0,
                            scope_note="s", method_note="m", interpretation="i")
    assert d.matched_percent is None
    assert d.unmatched_percent is None


def test_F4_rate_is_computed_honestly():
    d = MatchRateDisclosure(independent_records_examined=200, independent_records_matched=18,
                            scope_note="s", method_note="m", interpretation="i")
    assert d.matched_percent == 9.0
    assert d.unmatched_percent == 91.0


def test_finding_holds_records_and_differences_only():
    """A Finding is two cited records plus the fields on which they differ. There is no field
    for what the difference means or who is responsible."""
    names = {f.name for f in dataclasses.fields(Finding)}
    assert names == {"kind", "independent_record", "filing", "match", "differences",
                     "innocent_explanations", "caveat_key"}


def test_field_difference_republishes_both_values_and_grades_neither():
    names = {f.name for f in dataclasses.fields(FieldDifference)}
    assert {"filing_value", "independent_value"} <= names
    assert not any("score" in n or "severity" in n or "weight" in n for n in names)
