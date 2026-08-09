"""amendments.py -- compare a filing against a LATER VERSION OF ITSELF.

Kept in its own module, producing its own type (AmendmentObservation, not Finding), because it
is NOT a cross-source check. It compares the operator's own record to the operator's own later
record. It is not independent corroboration of anything, and it is excluded from the match
rate -- structurally, by not being a Finding, not merely by being labelled as one.

**Why it is here at all.** The failure this project exists to look for is a filed report that
is well-formed, verifiable, and still incomplete. A filer amending its own filing is the one
place in the public record where the filer itself identifies something its earlier filing did
not contain. That makes it the most direct public evidence available -- and simultaneously the
easiest thing in this project to over-read, because the ordinary reason a filing is amended is
that new information arrived and the record was corrected, which is the reporting system
working as designed.

So this module reports WHICH FIELDS CHANGED between versions and nothing else. It does not
rank amendments, does not flag any field as significant, and does not compute a rate.
"""
from __future__ import annotations

import dataclasses

from models import AmendmentObservation, FilingRecord

# Fields excluded from the comparison because they change on every amendment by definition --
# reporting them as "changed" would add noise to every observation and say nothing.
_STRUCTURAL_FIELDS = {"report_version", "submission_date", "source", "report_type"}

# Human labels for the fields that are compared. Anything not listed still gets compared,
# under its own attribute name.
_LABELS = {
    "report_id": "Report ID",
    "reporting_entity": "Reporting Entity",
    "incident_date": "Incident Date",
    "incident_time": "Incident Time",
    "city": "City",
    "state": "State",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "vin_prefix": "VIN",
    "make": "Make",
    "model": "Model",
    "model_year": "Model Year",
    "highest_injury_severity": "Highest Injury Severity Alleged",
    "airbags_deployed": "Any Air Bags Deployed?",
    "vehicle_towed": "Was Any Vehicle Towed?",
    "investigating_agency": "Investigating Agency",
    "narrative": "Narrative",
    "narrative_cbi": "Narrative - CBI?",
    "declared_data_availability": "Data Availability flags",
    "declared_sources": "Source flags",
}


def changed_fields(earlier: FilingRecord, later: FilingRecord) -> list:
    """Field labels whose values differ between two versions of the same report.

    The narrative is reported as changed or not changed; its text is never diffed word by word
    here. A word-level diff of an incident narrative invites exactly the reading this tool
    refuses to make -- that what was added should have been there the first time.
    """
    changed = []
    for field in dataclasses.fields(FilingRecord):
        if field.name in _STRUCTURAL_FIELDS:
            continue
        before, after = getattr(earlier, field.name), getattr(later, field.name)
        if before != after:
            changed.append(_LABELS.get(field.name, field.name))
    return changed


def observe(version_groups: dict) -> list:
    """Build one AmendmentObservation per version transition.

    `version_groups` maps report_id -> its versions in ascending order (from sources.sgo).
    A report amended twice produces two observations, v1->v2 and v2->v3, so the public record
    is followed as it actually happened rather than collapsed into first-vs-last.
    """
    observations = []
    for report_id, versions in sorted(version_groups.items()):
        for earlier, later in zip(versions, versions[1:]):
            observations.append(AmendmentObservation(
                report_id=report_id,
                reporting_entity=later.reporting_entity,
                from_version=earlier.report_version,
                to_version=later.report_version,
                from_submission_date=earlier.submission_date,
                to_submission_date=later.submission_date,
                changed_fields=changed_fields(earlier, later),
                caveat_key="AMENDMENT_NOTE",
            ))
    return observations
