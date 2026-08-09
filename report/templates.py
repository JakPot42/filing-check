"""templates.py -- render one finding or one amendment observation to a text block.

Document-subject grammar throughout: the subject of every sentence is a filing, a record, or a
difference -- never a company and never a company's conduct. Every block force-attaches its
caveat, and every cross-source finding force-attaches the innocent explanations.

Only facts and resolvable source references are interpolated. Nothing in this module explains
why a difference exists.
"""
from __future__ import annotations

import textwrap

import disclaimers
from models import AmendmentObservation, Finding, FindingKind

_INDENT = "  "


def _wrap(text: str, width: int = 74, indent: str = "  ", hang: str | None = None) -> str:
    """Wrap to a fixed width so the console output does not depend on terminal size.

    `hang` indents continuation lines further than the first, which is what keeps a bulleted
    innocent explanation readable as one item rather than running back to the margin."""
    return textwrap.fill(" ".join(text.split()), width=width,
                         initial_indent=indent,
                         subsequent_indent=hang if hang is not None else indent)


def _record_lines(record) -> str:
    bits = [
        f"{_INDENT}Independent record: NHTSA consumer complaint ODI {record.record_ref}",
        f"{_INDENT}  Filed by:      a member of the public (unverified self-report)",
        f"{_INDENT}  Manufacturer:  {record.entity_name}",
        f"{_INDENT}  Incident date: {record.incident_date or '(not stated)'}"
        f"   Complaint filed: {record.filed_date or '(not stated)'}",
    ]
    if record.vin_prefix:
        bits.append(f"{_INDENT}  VIN prefix:    {record.vin_prefix}")
    if record.components:
        bits.append(f"{_INDENT}  Components:    {record.components}")
    bits.append(f"{_INDENT}  Source:        {record.source_url}")
    return "\n".join(bits)


def _filing_lines(filing) -> str:
    return "\n".join([
        f"{_INDENT}Filing: SGO report {filing.report_id} version {filing.report_version}"
        f" ({filing.report_type})",
        f"{_INDENT}  Reporting entity: {filing.reporting_entity}",
        f"{_INDENT}  Incident date:    {filing.incident_date or '(not stated)'}"
        f"   Location: {filing.city or '(not stated)'}, {filing.state or ''}".rstrip(", "),
        f"{_INDENT}  Vehicle:          {filing.make} {filing.model} {filing.model_year}"
        f"   VIN prefix: {filing.vin_prefix or '(not stated)'}",
        f"{_INDENT}  Submitted:        {filing.submission_date or '(not stated)'}",
    ])


def _match_lines(match) -> str:
    return "\n".join([
        f"{_INDENT}Record linkage: {match.match_method}"
        f"   [confidence: {match.match_confidence}]",
        f"{_INDENT}  Basis: {match.gate_note}",
        f"{_INDENT}  This linkage is a candidate, not an established fact that the two",
        f"{_INDENT}  records describe the same event.",
    ])


def _explanations(finding: Finding) -> str:
    if not finding.innocent_explanations:
        return ""
    lines = [f"{_INDENT}WHY TWO PUBLIC RECORDS ROUTINELY DIFFER (read before the difference):"]
    for item in finding.innocent_explanations:
        lines.append(_wrap(f"- {item}", indent=f"{_INDENT}  ", hang=f"{_INDENT}    "))
    return "\n".join(lines)


def render_finding_block(finding: Finding) -> str:
    if finding.kind == FindingKind.UNMATCHED_INDEPENDENT_RECORD:
        header = "UNMATCHED INDEPENDENT RECORD -- no corresponding filing found in this snapshot"
        body = [header, _record_lines(finding.independent_record)]
    else:
        header = "CHECKABLE DIFFERENCE -- a matched pair of records differs"
        body = [header, _record_lines(finding.independent_record)]
        if finding.filing is not None:
            body.append(_filing_lines(finding.filing))
        if finding.match is not None:
            body.append(_match_lines(finding.match))
        if finding.differences:
            diff_lines = [f"{_INDENT}Fields that differ:"]
            for d in finding.differences:
                diff_lines.append(f"{_INDENT}  {d.field_label}:")
                diff_lines.append(f"{_INDENT}    filing      [{d.filing_field_name}]:"
                                  f" {d.filing_value}")
                diff_lines.append(f"{_INDENT}    independent [{d.independent_field_name}]:"
                                  f" {d.independent_value}")
            body.append("\n".join(diff_lines))

    explanations = _explanations(finding)
    if explanations:
        body.append(explanations)

    body.append(_wrap(disclaimers.get_caveat(finding.caveat_key)))

    if finding.match is not None and finding.match.match_confidence == "LOW":
        body.append(_wrap(disclaimers.LOW_CONFIDENCE))

    return "\n\n".join(part for part in body if part)


def render_amendment_block(obs: AmendmentObservation) -> str:
    fields = ", ".join(obs.changed_fields) if obs.changed_fields else "(no compared field changed)"
    body = [
        f"AMENDED FILING -- SGO report {obs.report_id},"
        f" version {obs.from_version} -> {obs.to_version}",
        "\n".join([
            f"{_INDENT}Reporting entity: {obs.reporting_entity}",
            f"{_INDENT}Submitted:        {obs.from_submission_date or '(not stated)'}"
            f"  ->  {obs.to_submission_date or '(not stated)'}",
        ]),
        _wrap(f"Fields that differ between the two versions: {fields}"),
        _wrap(disclaimers.AMENDMENT_NOTE),
    ]
    return "\n\n".join(body)
