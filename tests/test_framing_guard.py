"""Tests for framing_guard.py -- the output guard on tool-generated text.

Written and proven green BEFORE any reconciliation logic exists (the non-negotiable build
order inherited from claim-check and tie-check).

Three obligations checked here:
  1. every concealment/intent/duty-breach/character construction fires;
  2. the tool's own neutral vocabulary -- difference, discrepancy, unmatched, not present,
     amended, reporting threshold -- stays clean, because a guard that blocks the honest
     output is a guard that will be turned off;
  3. the guard is NOT the mechanism protecting the curated caveats. Those name concealment in
     order to disavow it and are verified by exact content in test_disclaimers.py instead.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from framing_guard import assert_clean, check_framing_violations

VIOLATIONS = [
    # concealment attributed to a filer
    "The company concealed the injury from its filing.",
    "They withheld the post-crash data.",
    "The operator covered up the severity of the collision.",
    "The manufacturer downplayed what happened.",
    # duty-breach claims
    "The filer failed to report this collision.",
    "The company failed to disclose the tow.",
    "Waymo neglected to file a report for this incident.",
    # under/mis-reporting
    "This operator underreported injuries during the period.",
    "The filing misreported the injury severity.",
    "The entity under-stated the number of crashes.",
    # evidence-of / proves constructions
    "There is evidence of concealment in this filing.",
    "This shows a pattern of wrongdoing.",
    "The difference proves the omission was deliberate.",
    "This indicates non-compliance with the Standing General Order.",
    # duty / regulation violation
    "The company violated the Standing General Order.",
    "This filer breached its reporting obligations.",
    # character judgments
    "The company is dishonest about its safety record.",
    "This manufacturer is negligent in its reporting.",
    "The reporting entity has been non-compliant.",
    # intent attribution
    "The narrative deliberately excluded the pedestrian contact.",
    "The filer knowingly omitted the tow information.",
    # company-level score
    "The company's transparency score is low.",
    "Their compliance rating should be downgraded.",
    # trust / enforcement
    "Readers cannot trust these filings.",
    "This company should be investigated by NHTSA.",
    "The operator must be fined for this.",
]


@pytest.mark.parametrize("text", VIOLATIONS)
def test_accusatory_constructions_fire(text):
    assert check_framing_violations(text), f"should have flagged: {text!r}"
    with pytest.raises(ValueError):
        assert_clean(text)


BENIGN = [
    # the tool's actual output vocabulary -- all of this must survive the guard
    "No corresponding filing was found in this snapshot for the independent record.",
    "The complaint records an injury; the filing records 'No Injured Reported'.",
    "This difference is checkable against both cited sources.",
    "A discrepancy in incident date of 2 days separates the two records.",
    "The independent record is unmatched against the filings in this snapshot.",
    "Tow status is not present in the filing.",
    "The filing was amended by its filer on 2026-04-02, from version 1 to version 2.",
    "Reporting thresholds differ between the two sources.",
    "The two sources capture different populations, so a difference is expected.",
    "The filing indicates that video data is available.",
    "The investigating agency named in the filing is the San Francisco Police Department.",
    "Both records place the incident in San Francisco, CA on 2026-03-04.",
    "Match basis: reporting entity exact, incident date within 1 day.",
    "This record could not be matched to any filing, and this may reflect source coverage.",
    "The filing reports property damage with no injured reported.",
    "Insurance liability is outside the scope of this comparison.",
]


@pytest.mark.parametrize("text", BENIGN)
def test_neutral_reconciliation_vocabulary_is_clean(text):
    assert check_framing_violations(text) == [], f"false positive on: {text!r}"
    assert_clean(text)


def test_difference_vocabulary_is_not_over_banned():
    # If the guard blocked its own product's words, it would be disabled in practice.
    for word in ("difference", "discrepancy", "unmatched", "not present", "amended",
                 "corresponding", "coverage", "liability"):
        assert check_framing_violations(f"The report notes a {word} here.") == [], word


def test_tier1_bans_concealment_words_even_when_negated():
    # In GENERATED prose these have no benign role. Stating the negated framing is the
    # curated caveats' job (they are never passed through this guard).
    assert check_framing_violations("This is not evidence of concealment.")
    assert check_framing_violations("No omission is implied by this difference.")
    assert check_framing_violations("The filer did not underreport anything.")


def test_omit_is_banned_but_not_present_is_the_sanctioned_phrasing():
    # "omitted" presupposes the item belonged in the filing -- a duty claim. The neutral
    # phrasing carries the same information without it, and the templates use it.
    assert check_framing_violations("The filing omitted the tow status.")
    assert check_framing_violations("Tow status is not present in the filing.") == []


def test_quoted_source_text_is_the_renderers_responsibility_not_the_guards():
    # A consumer complaint may itself allege a cover-up. That text is the complainant's,
    # quoted and attributed -- the renderer must never route it through this guard. Here we
    # only assert the guard WOULD reject it, which is why the boundary has to exist.
    complainant_words = "the manufacturer covered up the defect"
    assert check_framing_violations(complainant_words)


def test_assert_clean_returns_none_on_clean_text():
    assert assert_clean("No corresponding filing was found for this independent record.") is None
