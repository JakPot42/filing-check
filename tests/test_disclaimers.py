"""Exact-content tests for the curated caveats.

These strings are NOT protected by framing_guard -- several of them name concealment and
intent in order to disavow them, which would trip the guard's lemma layer by design. This file
is the mechanism that protects them instead, so the two layers together leave no gap.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import disclaimers
from framing_guard import check_framing_violations


def _flat(text: str) -> str:
    """Collapse the hard wrapping used for console display, so content assertions test the
    words rather than where the line breaks fall."""
    return " ".join(text.split())


def test_every_caveat_is_nonempty_and_registered():
    for key, text in disclaimers.CAVEATS.items():
        assert text.strip(), f"{key} is empty"
        assert disclaimers.get_caveat(key) == text


def test_unknown_caveat_key_is_a_hard_error():
    with pytest.raises(KeyError):
        disclaimers.get_caveat("NOT_A_KEY")
    assert disclaimers.get_caveat(None) == ""


def test_finding_note_disavows_wrongdoing_intent_and_concealment():
    t = _flat(disclaimers.FINDING_NOTE)
    assert "not a determination that either document is wrong" in t
    assert "concealed" in t          # named in order to be disavowed
    assert "with intent" in t
    assert "cited above so the comparison can be checked" in t


def test_unmatched_note_refuses_the_missing_filing_inference():
    t = _flat(disclaimers.UNMATCHED_NOTE)
    assert "not evidence that a filing is missing" in t
    assert "this tool does not claim it is" in t
    assert "too strict" in t, "the method's own limits must be offered before any other reading"


def test_amendment_note_marks_itself_as_not_a_cross_source_check():
    t = _flat(disclaimers.AMENDMENT_NOTE)
    assert "LATER VERSION OF ITSELF" in t
    assert "excluded from the match rate" in t
    assert "the reporting system working as intended" in t


def test_header_states_no_per_company_score_or_rate():
    assert "no per-company score and no per-company match rate" in \
        disclaimers.HEADER_WHAT_IT_IS_NOT
    assert "not a statement about any company's honesty, intent, or compliance" in \
        disclaimers.HEADER_WHAT_IT_IS_NOT


def test_scope_disclaimer_refuses_the_correctness_verdict():
    t = _flat(disclaimers.SCOPE_DISCLAIMER)
    assert "does not determine whether a filing was correct" in t
    assert "not a finding of wrongdoing" in t
    assert "no score or rate for any company" in t


def test_innocent_explanations_cover_the_four_named_in_the_spec():
    """Reporting thresholds, timing, source error, and duplicates are named explicitly in the
    project's framing constraint. All four must be present, plus the two this build added."""
    blob = _flat(" ".join(disclaimers.INNOCENT_EXPLANATIONS)).lower()
    for required in ("reporting threshold", "timing", "error", "duplicate"):
        assert required in blob, f"missing innocent explanation: {required}"
    # added by this build, from what the data actually looks like
    assert "capture different things" in blob
    assert "linkage itself may be wrong" in blob
    assert len(disclaimers.INNOCENT_EXPLANATIONS) >= 6


def test_match_rate_interpretation_pre_authorises_the_low_result():
    """The negative result is disclosed as expected, not explained away after the fact."""
    t = _flat(disclaimers.MATCH_RATE_INTERPRETATION)
    assert "A LOW match rate is the expected result" in t
    assert "expected before this tool was written" in t
    assert "not a completeness measure, not an error rate" in t
    assert "never broken out by company" in t
    assert "no owner to file one" in t, "the structural non-overlap must be stated, not implied"


def test_match_rate_benchmark_carries_the_emir_figure():
    t = _flat(disclaimers.MATCH_RATE_BENCHMARK)
    assert "55%" in t
    assert "four years" in t
    assert "not a defect in this tool or in any filer" in t


def test_known_gaps_name_the_two_populations_that_were_wanted_but_unavailable():
    blob = _flat(" ".join(disclaimers.KNOWN_GAPS))
    assert "SWITRS" in blob and "requires an account" in blob
    assert "OL 316" in blob and "no longer reachable" in blob
    assert "built from NHTSA SGO data" in blob, (
        "the circularity of the DMV's current collision-reports link is the reason that "
        "population is excluded, and must be stated"
    )
    assert "single-source scope is the most important limit" in blob


def test_absence_is_not_read_as_a_clean_bill_of_health():
    t = _flat(disclaimers.ABSENCE)
    assert "not a confirmation that" in t
    assert "Coverage of both populations is incomplete" in t


def test_the_guard_exemption_is_needed_by_exactly_two_caveats():
    """Documents the boundary in an executable way, and keeps it narrow.

    FINDING_NOTE has to name concealment, and SCOPE_DISCLAIMER has to name wrongdoing, in
    order to disavow them -- so both trip the guard's lemma layer by design. That is why the
    renderer must never route the curated caveats through the guard, and why this file
    protects them instead.

    Every OTHER caveat turns out to be clean: they refuse the accusatory reading using only
    neutral vocabulary. That is worth pinning down, because it keeps the exemption at two
    strings rather than a general licence, and a future edit that makes another caveat
    dependent on it is a change worth noticing."""
    for name in ("FINDING_NOTE", "SCOPE_DISCLAIMER"):
        assert check_framing_violations(getattr(disclaimers, name)), (
            f"{name} names concealment/wrongdoing in order to disavow it -- if it stops "
            f"tripping the guard, check that it still actually disavows it"
        )
    for name in ("UNMATCHED_NOTE", "AMENDMENT_NOTE", "MATCH_RATE_INTERPRETATION",
                 "MATCH_RATE_BENCHMARK", "FOOTER", "ABSENCE", "LOW_CONFIDENCE",
                 "HEADER_WHAT_IT_IS", "HEADER_WHAT_IT_IS_NOT"):
        assert check_framing_violations(getattr(disclaimers, name)) == [], (
            f"{name} now depends on the guard exemption -- it previously stated its refusal "
            f"in neutral vocabulary. Prefer rewording it back over widening the exemption."
        )


def test_scope_disclaimer_is_ascii_safe():
    """Windows cp1252 lesson from the installation-resilience build: no smart punctuation in
    anything that reaches a console."""
    for name in ("SCOPE_DISCLAIMER", "HEADER_WHAT_IT_IS", "HEADER_WHAT_IT_IS_NOT", "FOOTER",
                 "FINDING_NOTE", "UNMATCHED_NOTE", "AMENDMENT_NOTE", "LOW_CONFIDENCE",
                 "ABSENCE", "MATCH_RATE_INTERPRETATION", "MATCH_RATE_BENCHMARK"):
        text = getattr(disclaimers, name)
        text.encode("cp1252")  # raises UnicodeEncodeError on a smart quote or em-dash
    for group in (disclaimers.INNOCENT_EXPLANATIONS, disclaimers.KNOWN_GAPS):
        for item in group:
            item.encode("cp1252")
