"""crosscheck.py -- the tracing direction, made into a check.

Auditing distinguishes *vouching* (start from the records, work backward -- catches
overstatement) from *tracing* (start from an INDEPENDENT population, work forward INTO the
records -- catches omission). Only tracing can reach a record that is present, well-formed,
and still incomplete, so this module runs in exactly one direction:

    for each independent record -> look for a corresponding filing

Never the reverse. A filing with no complaint against it is not a finding and is not computed
here: consumer complaints exist for a tiny and non-random slice of vehicles, so "no complaint
corresponds to this filing" is the normal state of almost every filing and means nothing.

Two outcomes, and no third:
  - a corresponding filing was found -> compare the fields both sources carry
  - none was found -> record that, with the reasons it usually happens attached

Neither outcome is a conclusion about a filer, and there is no model field in which to store
one (see models.py).
"""
from __future__ import annotations

import config
import disclaimers
from models import FieldDifference, Finding, FindingKind
from resolve.incident_resolver import best_link, build_index


def _injury_state(filing) -> bool | None:
    """True = an injury is reported, False = none reported, None = the filing says nothing.

    None is the important case: 'Unknown' is the injury severity on the large majority of
    Level 2 filings, and treating it as 'no injury' would generate false differences at scale.
    """
    value = (filing.highest_injury_severity or "").strip()
    if value in config.INJURY_INDETERMINATE:
        return None
    return value not in config.FILING_NO_INJURY_VALUES


def _record_injury_state(record) -> bool | None:
    if record.injuries_reported is None:
        return None
    return record.injuries_reported > 0


def _fatality_state(filing) -> bool | None:
    value = (filing.highest_injury_severity or "").strip()
    if value in config.INJURY_INDETERMINATE:
        return None
    return value == config.FILING_FATALITY_VALUE


def _record_fatality_state(record) -> bool | None:
    if record.deaths_reported is None:
        return None
    return record.deaths_reported > 0


def compare_fields(filing, record) -> list:
    """Fields where the two records disagree, both values republished as written.

    A comparison is skipped entirely whenever either side is indeterminate. An indeterminate
    field is not a disagreement, and reporting it as one would be the single easiest way for
    this tool to manufacture findings.
    """
    differences = []

    if "injury" in config.COMPARED_FIELDS:
        f_state, r_state = _injury_state(filing), _record_injury_state(record)
        if f_state is not None and r_state is not None and f_state != r_state:
            differences.append(FieldDifference(
                field_label="Injury reported",
                filing_value=filing.highest_injury_severity or "(blank)",
                independent_value=f"{record.injuries_reported} injuries reported",
                filing_field_name="Highest Injury Severity Alleged",
                independent_field_name="numberOfInjuries",
            ))

    if "fatality" in config.COMPARED_FIELDS:
        f_state, r_state = _fatality_state(filing), _record_fatality_state(record)
        if f_state is not None and r_state is not None and f_state != r_state:
            differences.append(FieldDifference(
                field_label="Fatality reported",
                filing_value=filing.highest_injury_severity or "(blank)",
                independent_value=f"{record.deaths_reported} deaths reported",
                filing_field_name="Highest Injury Severity Alleged",
                independent_field_name="numberOfDeaths",
            ))

    return differences


def trace(records: list, filings: list) -> tuple:
    """Trace every independent record into the filings.

    Returns (findings, matched_count). `matched_count` is the number of independent records
    linked to a filing -- the numerator of the match rate. Findings are produced for unmatched
    records and for matched pairs that differ; a matched pair that agrees is a clean
    reconciliation and is counted, not reported.
    """
    findings = []
    matched_count = 0
    index = build_index(filings)
    by_id = {(f.report_id, f.report_version): f for f in filings}
    entity_cache: dict = {}

    for record in records:
        match = best_link(record, index, entity_cache)
        if match is None:
            findings.append(Finding(
                kind=FindingKind.UNMATCHED_INDEPENDENT_RECORD,
                independent_record=record,
                filing=None,
                match=None,
                differences=[],
                innocent_explanations=list(disclaimers.INNOCENT_EXPLANATIONS),
                caveat_key="UNMATCHED_NOTE",
            ))
            continue

        matched_count += 1
        filing = by_id.get((match.filing_report_id, match.filing_version))
        differences = compare_fields(filing, record) if filing else []
        if differences:
            findings.append(Finding(
                kind=FindingKind.FIELD_DIFFERENCE,
                independent_record=record,
                filing=filing,
                match=match,
                differences=differences,
                innocent_explanations=list(disclaimers.INNOCENT_EXPLANATIONS),
                caveat_key="FINDING_NOTE",
            ))

    return findings, matched_count
