"""Tests for the reconciliation layer: tracing, amendments, and the coverage disclosure.

The three things most worth pinning down here are refusals, not capabilities:
  - an indeterminate field is never reported as a disagreement;
  - the trace runs in one direction only, and a filing without a complaint is never a finding;
  - amendments structurally cannot reach the match rate.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from models import AmendmentObservation, FilingRecord, FindingKind, IndependentRecord, Population
from reconcile import amendments as amendments_mod
from reconcile import coverage as coverage_mod
from reconcile.crosscheck import compare_fields, trace


def _filing(entity="Tesla, Inc.", vin="5YJ3E1EA5LF", date="OCT-2025", report_id="R1",
            version="1", severity="Property Damage. No Injured Reported", **kw):
    return FilingRecord(report_id=report_id, report_version=version, reporting_entity=entity,
                        report_type="ADAS", incident_date=date, vin_prefix=vin,
                        highest_injury_severity=severity, **kw)


def _record(entity="Tesla, Inc.", vin="5YJ3E1EA5LF", date="10/14/2025", ref="1001",
            injuries=0, deaths=0):
    return IndependentRecord(population_id=Population.NHTSA_COMPLAINTS, record_ref=ref,
                             entity_name=entity, incident_date=date, vin_prefix=vin,
                             is_crash=True, injuries_reported=injuries, deaths_reported=deaths)


# --- field comparison ---------------------------------------------------------

def test_injury_disagreement_is_reported_with_both_values_republished():
    diffs = compare_fields(_filing(severity="No Injured Reported"), _record(injuries=1))
    assert len(diffs) == 1
    assert diffs[0].field_label == "Injury reported"
    assert diffs[0].filing_value == "No Injured Reported"
    assert "1 injuries reported" in diffs[0].independent_value
    # the literal source field names travel with the difference, so it stays checkable
    assert diffs[0].filing_field_name == "Highest Injury Severity Alleged"
    assert diffs[0].independent_field_name == "numberOfInjuries"


def test_agreement_produces_no_difference():
    assert compare_fields(_filing(severity="No Injured Reported"), _record(injuries=0)) == []
    assert compare_fields(_filing(severity="Minor W/ Hospitalization"),
                          _record(injuries=2)) == []


@pytest.mark.parametrize("severity", list(config.INJURY_INDETERMINATE))
def test_an_indeterminate_filing_value_is_never_a_disagreement(severity):
    """'Unknown' is the injury severity on the large majority of Level 2 filings. Treating it
    as 'no injury' would manufacture false differences at scale -- against named companies."""
    assert compare_fields(_filing(severity=severity), _record(injuries=3)) == []
    assert compare_fields(_filing(severity=severity), _record(injuries=0)) == []


def test_an_indeterminate_independent_value_is_never_a_disagreement():
    record = _record(injuries=None, deaths=None)
    assert compare_fields(_filing(severity="No Injured Reported"), record) == []


def test_fatality_disagreement_is_reported():
    diffs = compare_fields(_filing(severity="No Injured Reported"), _record(deaths=1))
    labels = [d.field_label for d in diffs]
    assert "Fatality reported" in labels


# --- tracing ------------------------------------------------------------------

def test_unmatched_record_becomes_a_finding_with_its_explanations_attached():
    findings, matched = trace([_record(vin="ZZZZZZZZZZZ")], [_filing()])
    assert matched == 0
    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == FindingKind.UNMATCHED_INDEPENDENT_RECORD
    assert finding.filing is None
    assert finding.caveat_key == "UNMATCHED_NOTE"
    assert len(finding.innocent_explanations) >= 6


def test_a_matched_pair_that_agrees_is_counted_but_not_reported():
    findings, matched = trace([_record(injuries=0)],
                              [_filing(severity="No Injured Reported")])
    assert matched == 1
    assert findings == [], "a clean reconciliation is not a finding"


def test_a_matched_pair_that_differs_becomes_a_finding_carrying_both_records():
    findings, matched = trace([_record(injuries=1)],
                              [_filing(severity="No Injured Reported")])
    assert matched == 1
    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == FindingKind.FIELD_DIFFERENCE
    assert finding.filing is not None and finding.match is not None
    assert finding.caveat_key == "FINDING_NOTE"


def test_trace_runs_in_one_direction_only():
    """A filing with no corresponding complaint is not a finding and is not counted. Consumer
    complaints exist for a small, non-random slice of vehicles, so 'no complaint corresponds
    to this filing' is the normal state of almost every filing and means nothing."""
    findings, matched = trace([], [_filing(), _filing(report_id="R2"), _filing(report_id="R3")])
    assert findings == []
    assert matched == 0


def test_matched_count_counts_records_not_findings():
    records = [_record(ref="a", injuries=0), _record(ref="b", injuries=1)]
    findings, matched = trace(records, [_filing(severity="No Injured Reported")])
    assert matched == 2, "both records linked"
    assert len(findings) == 1, "only the disagreeing one is reported"


# --- amendments ---------------------------------------------------------------

def test_amendment_observation_lists_changed_fields():
    v1 = _filing(version="1", severity="Unknown", report_id="X")
    v2 = _filing(version="2", severity="Minor W/ Hospitalization", report_id="X",
                 investigating_agency="Some PD")
    observations = amendments_mod.observe({"X": [v1, v2]})
    assert len(observations) == 1
    obs = observations[0]
    assert obs.from_version == "1" and obs.to_version == "2"
    assert "Highest Injury Severity Alleged" in obs.changed_fields
    assert "Investigating Agency" in obs.changed_fields
    assert obs.caveat_key == "AMENDMENT_NOTE"


def test_each_version_transition_is_its_own_observation():
    versions = [_filing(version=str(i), report_id="X", severity=f"s{i}") for i in (1, 2, 3)]
    observations = amendments_mod.observe({"X": versions})
    assert [(o.from_version, o.to_version) for o in observations] == [("1", "2"), ("2", "3")]


def test_report_version_and_submission_date_are_not_reported_as_changes():
    """They change on every amendment by definition; listing them would add noise to every
    observation and say nothing."""
    v1 = _filing(version="1", report_id="X")
    v2 = _filing(version="2", report_id="X")
    v2.submission_date = "NOV-2025"
    obs = amendments_mod.observe({"X": [v1, v2]})[0]
    assert obs.changed_fields == []


def test_an_amendment_is_not_a_finding_and_cannot_enter_the_findings_list():
    obs = amendments_mod.observe({"X": [_filing(version="1", report_id="X"),
                                        _filing(version="2", report_id="X",
                                                severity="Fatality")]})[0]
    assert isinstance(obs, AmendmentObservation)
    assert not hasattr(obs, "kind"), "an amendment has no FindingKind, so it cannot be traced"


# --- the coverage disclosure --------------------------------------------------

def test_coverage_carries_its_interpretation_and_benchmark():
    disclosure = coverage_mod.build(100, 4, "scope", "method")
    assert disclosure.matched_percent == 4.0
    assert disclosure.unmatched_percent == 96.0
    assert "A LOW match rate is the expected result" in disclosure.interpretation
    assert "55%" in disclosure.benchmark_note


def test_coverage_module_never_sees_amendments():
    """Decision-module purity check. The exclusion of amendments from the match rate is structural:
    there is no parameter through which one could enter, and this module's source does not
    mention them."""
    source_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "reconcile", "coverage.py")
    with open(source_path, encoding="utf-8") as fh:
        # the module docstring explains the exclusion; the CODE must not touch amendments
        source = fh.read()
    body = source.split('"""', 2)[-1]
    assert "amendment" not in body.lower(), (
        "coverage.py's code references amendments -- the match rate must be computed without "
        "them, structurally"
    )
    import inspect
    params = set(inspect.signature(coverage_mod.build).parameters)
    assert params == {"records_examined", "records_matched", "scope_note", "method_note"}


def test_coverage_module_never_sees_a_company():
    """The no-per-company-rate decision, checked at the module boundary as well as on the
    model. Neither build() nor method_note() takes an entity."""
    import inspect
    for fn in (coverage_mod.build, coverage_mod.method_note):
        for name in inspect.signature(fn).parameters:
            for root in ("entity", "company", "filer", "operator", "manufacturer"):
                assert root not in name.lower(), f"{fn.__name__}({name}) names a company"


def test_method_note_leads_with_the_methods_own_limits():
    note = coverage_mod.method_note(month_tolerance=1, high_confidence_methods=(),
                                    configurations_resolved=140, configurations_total=176)
    assert "traced INTO the filings" in note
    assert "reverse" in note
    assert "NO linkage here is high confidence" in note
    assert "140 of 176" in note
    assert "could not be queried at all" in note, (
        "a configuration that could not be queried has an ABSENT independent population, not "
        "an empty one -- the rate cannot distinguish them, so the note must say so"
    )
