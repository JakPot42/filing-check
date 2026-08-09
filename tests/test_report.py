"""Tests for the report layer.

The report is where the framing either holds or fails in front of a reader, so these tests
check the output itself rather than the intent behind it: every finding carries its caveat and
its explanations, the match rate cannot appear without its interpretation, amendments are
visibly separated from cross-source findings, and no rendered text ever trips the guard.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import disclaimers
from framing_guard import check_framing_violations
from models import (
    AmendmentObservation,
    FieldDifference,
    FilingRecord,
    Finding,
    FindingKind,
    IndependentRecord,
    Population,
    ReconciliationReport,
    SourceRef,
)
from reconcile import coverage as coverage_mod
from report.render import render_text, to_json
from report.templates import render_amendment_block, render_finding_block

_SOURCE = SourceRef(source_id="NHTSA_SGO", name="SGO filings", url="https://example.gov/sgo",
                    retrieved_date="2026-08-09", snapshot_label="ADAS CSV, 2026-08-09")


def _filing():
    return FilingRecord(report_id="13781-12029", report_version="2",
                        reporting_entity="Tesla, Inc.", report_type="ADAS",
                        incident_date="OCT-2025", city="Hesperia", state="CA",
                        vin_prefix="5YJ3E1EA5LF", make="TESLA", model="Model 3",
                        model_year="2020",
                        highest_injury_severity="Property Damage. No Injured Reported",
                        submission_date="OCT-2025", source=_SOURCE)


def _record(summary=""):
    return IndependentRecord(population_id=Population.NHTSA_COMPLAINTS, record_ref="11693937",
                             entity_name="Tesla, Inc.", incident_date="10/14/2025",
                             filed_date="10/20/2025", vin_prefix="5YJ3E1EA5LF", is_crash=True,
                             injuries_reported=1, deaths_reported=0,
                             summary_quoted=summary,
                             source_url="https://www.nhtsa.gov/?nhtsaId=11693937")


def _difference_finding(summary=""):
    from models import Match
    return Finding(
        kind=FindingKind.FIELD_DIFFERENCE,
        independent_record=_record(summary),
        filing=_filing(),
        match=Match(filing_report_id="13781-12029", filing_version="2",
                    independent_record_ref="11693937", match_method="VIN_PREFIX_MONTH",
                    match_score=100, match_confidence="LOW", date_delta_months=0,
                    gate_note="same reporting entity; shared VIN prefix"),
        differences=[FieldDifference(field_label="Injury reported",
                                     filing_value="Property Damage. No Injured Reported",
                                     independent_value="1 injuries reported",
                                     filing_field_name="Highest Injury Severity Alleged",
                                     independent_field_name="numberOfInjuries")],
        innocent_explanations=list(disclaimers.INNOCENT_EXPLANATIONS),
        caveat_key="FINDING_NOTE",
    )


def _unmatched_finding():
    return Finding(kind=FindingKind.UNMATCHED_INDEPENDENT_RECORD, independent_record=_record(),
                   innocent_explanations=list(disclaimers.INNOCENT_EXPLANATIONS),
                   caveat_key="UNMATCHED_NOTE")


def _report(findings=None, amendments=None, examined=1181, matched=44):
    return ReconciliationReport(
        findings=findings if findings is not None else [_difference_finding()],
        amendments=amendments or [],
        coverage=coverage_mod.build(examined, matched, "scope note", "method note"),
        sources=[_SOURCE], scope_note="test scope",
        known_gaps=list(disclaimers.KNOWN_GAPS),
        generated="2026-08-09", tool="filingcheck", version="0.1.0",
    )


# --- every block carries its mandatory caveat ---------------------------------

def test_difference_block_force_attaches_its_caveat_and_explanations():
    block = render_finding_block(_difference_finding())
    assert "not a determination that either document is wrong" in " ".join(block.split())
    assert "WHY TWO PUBLIC RECORDS ROUTINELY DIFFER" in block
    assert "Reporting thresholds differ" in " ".join(block.split())


def test_difference_block_shows_both_values_and_both_source_field_names():
    block = render_finding_block(_difference_finding())
    assert "Highest Injury Severity Alleged" in block
    assert "numberOfInjuries" in block
    assert "Property Damage. No Injured Reported" in block
    assert "1 injuries reported" in block


def test_difference_block_cites_both_records_so_a_reader_can_retrieve_them():
    block = render_finding_block(_difference_finding())
    assert "ODI 11693937" in block
    assert "https://www.nhtsa.gov/?nhtsaId=11693937" in block
    assert "SGO report 13781-12029 version 2" in block


def test_a_low_confidence_linkage_attaches_the_low_confidence_caveat():
    block = render_finding_block(_difference_finding())
    assert "Verify that both records describe the same event" in " ".join(block.split())


def test_unmatched_block_refuses_the_missing_filing_inference():
    block = render_finding_block(_unmatched_finding())
    flat = " ".join(block.split())
    assert "no corresponding filing found" in flat.lower()
    assert "not evidence that a filing is missing" in flat


def test_amendment_block_states_it_is_not_a_cross_source_check():
    obs = AmendmentObservation(report_id="X", reporting_entity="Tesla, Inc.", from_version="1",
                               to_version="2", changed_fields=["Narrative"],
                               caveat_key="AMENDMENT_NOTE")
    block = render_amendment_block(obs)
    flat = " ".join(block.split())
    assert "LATER VERSION OF ITSELF" in flat
    assert "excluded from the match rate" in flat
    assert "Narrative" in block


# --- the match rate is never separable from its interpretation ----------------

def test_text_report_shows_the_rate_with_its_interpretation_and_benchmark():
    text = render_text(_report())
    flat = " ".join(text.split())
    assert "MATCH RATE: 3.7%" in flat
    assert "96.3% were not linked" in flat
    assert "A LOW match rate is the expected result" in flat
    assert "55%" in flat


def test_the_rate_appears_before_the_findings():
    """A reader who meets a list of differences first has already formed an impression the
    coverage statistic then has to argue against."""
    text = render_text(_report())
    assert text.index("MATCH RATE") < text.index("CROSS-SOURCE FINDINGS")


def test_json_export_cannot_carry_the_number_without_the_words():
    payload = to_json(_report())
    rate = payload["match_rate"]
    assert rate["matched_percent"] == 3.7
    assert "A LOW match rate is the expected result" in rate["interpretation"]
    assert "55%" in rate["benchmark_note"]
    assert rate["per_company_breakdown"] is None
    assert "by design" in rate["per_company_breakdown_note"]


def test_an_empty_population_reports_no_rate_rather_than_zero():
    text = render_text(_report(findings=[], examined=0, matched=0))
    assert "not computed" in text
    assert to_json(_report(findings=[], examined=0, matched=0))["match_rate"][
        "matched_percent"] is None


# --- amendments stay visibly separate -----------------------------------------

def test_amendments_are_rendered_in_their_own_labelled_section():
    obs = AmendmentObservation(report_id="X", reporting_entity="Tesla, Inc.", from_version="1",
                               to_version="2", changed_fields=["Narrative"])
    text = render_text(_report(amendments=[obs]))
    assert "AMENDED FILINGS" in text
    assert text.index("CROSS-SOURCE FINDINGS") < text.index("AMENDED FILINGS")
    assert "NOT a cross-source check" in text


def test_json_amendments_are_a_separate_key_from_findings():
    obs = AmendmentObservation(report_id="X", reporting_entity="Tesla, Inc.", from_version="1",
                               to_version="2", changed_fields=["Narrative"])
    payload = to_json(_report(amendments=[obs]))
    assert payload["findings"] and payload["amendments"]["observations"]
    assert "excluded from the match rate" in payload["amendments"]["note"]
    kinds = {f["kind"] for f in payload["findings"]}
    assert "AMENDMENT" not in kinds


# --- absence and gaps ---------------------------------------------------------

def test_no_findings_is_not_rendered_as_a_clean_bill_of_health():
    text = render_text(_report(findings=[]))
    assert "NO CROSS-SOURCE FINDINGS" in text
    assert "not a confirmation that" in " ".join(text.split())


def test_known_gaps_are_shown_in_the_report_not_just_the_docs():
    text = render_text(_report())
    flat = " ".join(text.split())
    assert "KNOWN COVERAGE GAPS" in text
    assert "SWITRS" in flat and "OL 316" in flat


# --- the guard boundary, checked on real rendered output ----------------------

def _flat(text: str) -> str:
    return " ".join(text.split())


def _without_exempt_caveats(text: str) -> str:
    """Rendered text minus the two curated caveats that name concealment/wrongdoing in order
    to disavow them. The renderer hard-wraps them, so this compares on flattened whitespace."""
    flat = _flat(text)
    for exempt in (disclaimers.FINDING_NOTE, disclaimers.SCOPE_DISCLAIMER,
                   disclaimers.MATCH_RATE_INTERPRETATION, disclaimers.UNMATCHED_NOTE,
                   disclaimers.AMENDMENT_NOTE, disclaimers.LOW_CONFIDENCE,
                   disclaimers.ABSENCE, disclaimers.FOOTER,
                   disclaimers.HEADER_WHAT_IT_IS, disclaimers.HEADER_WHAT_IT_IS_NOT,
                   disclaimers.MATCH_RATE_BENCHMARK,
                   *disclaimers.INNOCENT_EXPLANATIONS, *disclaimers.KNOWN_GAPS):
        flat = flat.replace(_flat(exempt), " ")
    return flat


def test_a_generated_narrative_that_violates_the_framing_is_discarded_not_repaired():
    bad = "The company concealed the injury and failed to report it."
    text = render_text(_report(), narrative=bad)
    assert "PLAIN-LANGUAGE SUMMARY" not in text
    # the narrative's own words never reach the reader; the only surviving "concealed" is the
    # curated caveat that disavows it
    assert "concealed the injury" not in _flat(text)
    assert to_json(_report(), narrative=bad)["narrative"] is None


def test_a_clean_generated_narrative_is_shown():
    good = ("One independent record was linked to a filing, and the two records differ on "
            "whether an injury was reported.")
    text = render_text(_report(), narrative=good)
    assert "PLAIN-LANGUAGE SUMMARY" in text


def test_a_complainants_own_allegation_is_republished_and_attributed_not_laundered():
    """A complaint may itself allege a cover-up. That text is the complainant's, quoted and
    attributed -- it must reach the reader, and it must never be routed through the guard or
    restated as this tool's own words."""
    allegation = "The manufacturer covered up the defect and failed to disclose it."
    payload = to_json(_report(findings=[_difference_finding(summary=allegation)]))
    quoted = payload["findings"][0]["independent_record"]
    assert quoted["summary_quoted"] == allegation
    assert "own words" in quoted["summary_quoted_note"]
    # ...and the guard would have rejected it, which is exactly why the boundary must exist
    assert check_framing_violations(allegation)


def test_the_tools_own_rendered_prose_is_clean_of_accusatory_language():
    """Everything the tool writes itself -- headers, labels, method notes, the coverage block
    -- must pass its own guard. The two curated caveats that name concealment to disavow it
    are excluded, since they are verified by exact content instead."""
    text = render_text(_report(amendments=[
        AmendmentObservation(report_id="X", reporting_entity="Tesla, Inc.", from_version="1",
                             to_version="2", changed_fields=["Narrative"])]))
    residue = _without_exempt_caveats(text)
    assert check_framing_violations(residue) == [], (
        "the tool's own rendered prose must survive its own guard"
    )
