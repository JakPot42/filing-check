"""render.py -- assemble the full report (text + JSON).

Structure, in the order a reader meets it:
  header (what it is / what it is not) -> THE MATCH RATE, with its interpretation ->
  cross-source findings -> amendment observations, separately labelled -> known gaps -> footer

**The match rate comes before the findings deliberately.** A reader who sees a list of
differences first and the coverage statistic last has already formed an impression the
statistic then has to argue against. The rate is the context for reading everything below it,
so it is placed where context belongs.

The framing guard is applied only to an optional tool-generated narrative -- never to the
curated caveats (two of which name concealment and wrongdoing in order to disavow them), and
never to source text republished from the public record, including a complainant's own words.
"""
from __future__ import annotations

import textwrap

import config
import disclaimers
from framing_guard import assert_clean
from models import ReconciliationReport
from report.templates import render_amendment_block, render_finding_block

_RULE = "-" * 74


def _header(report: ReconciliationReport) -> str:
    sources = "\n".join(
        f"  - {s.name}\n      {s.url}\n      {s.snapshot_label}" for s in report.sources
    ) or "  (none)"
    return (
        "FILING RECONCILIATION REPORT\n"
        f"Scope:      {report.scope_note}\n"
        f"Generated:  {report.generated}   Tool: {report.tool} v{report.version}\n"
        f"Sources:\n{sources}\n\n"
        f"{disclaimers.HEADER_WHAT_IT_IS}\n\n"
        f"{disclaimers.HEADER_WHAT_IT_IS_NOT}"
    )


def _coverage_block(report: ReconciliationReport) -> str:
    coverage = report.coverage
    if coverage is None:
        return ""
    matched = coverage.matched_percent
    if matched is None:
        headline = ("MATCH RATE: not computed -- no independent records were examined in this "
                    "scope.")
    else:
        headline = (
            f"MATCH RATE: {matched}% of independent records were linked to a filing "
            f"({coverage.independent_records_matched} of "
            f"{coverage.independent_records_examined}).\n"
            f"            {coverage.unmatched_percent}% were not linked."
        )
    parts = [headline, coverage.method_note, coverage.interpretation]
    if coverage.benchmark_note:
        parts.append(_wrap(coverage.benchmark_note))
    return "\n\n".join(p for p in parts if p)


def _wrap(text: str, width: int = 74, indent: str = "  ", hang: str | None = None) -> str:
    """Wrap to a fixed width so the console output does not depend on terminal size."""
    return textwrap.fill(" ".join(text.split()), width=width,
                         initial_indent=indent,
                         subsequent_indent=hang if hang is not None else indent)


def _gaps_block(report: ReconciliationReport) -> str:
    if not report.known_gaps:
        return ""
    lines = ["KNOWN COVERAGE GAPS -- what this report could not look at"]
    for gap in report.known_gaps:
        lines.append(_wrap(f"- {gap}", hang="    "))
    return "\n".join(lines)


def _footer() -> str:
    return f"{_RULE}\n{disclaimers.FOOTER}\n{_RULE}"


def _gate(narrative: str) -> str | None:
    """Any tool-generated narrative passes the framing guard or is discarded entirely.

    Discarded, not repaired: a narrative that has drifted into attributing concealment or
    intent cannot be patched into safety, and the deterministic report above it already
    carries the whole finding."""
    try:
        assert_clean(narrative)
        return narrative
    except ValueError:
        return None


def render_text(report: ReconciliationReport, narrative: str | None = None) -> str:
    parts = [_header(report), _RULE]

    coverage = _coverage_block(report)
    if coverage:
        parts.extend([coverage, _RULE])

    if report.findings:
        parts.append("CROSS-SOURCE FINDINGS")
        parts.append("")
        for finding in report.findings:
            parts.append(render_finding_block(finding))
            parts.append("")
    else:
        parts.append("NO CROSS-SOURCE FINDINGS\n" + _wrap(disclaimers.ABSENCE))
        parts.append("")

    parts.append(_RULE)
    if report.amendments:
        parts.append(
            "AMENDED FILINGS -- a filing compared against a later version of ITSELF.\n"
            "This section is NOT a cross-source check and is excluded from the match rate\n"
            "above. It is listed separately for exactly that reason."
        )
        parts.append("")
        for obs in report.amendments:
            parts.append(render_amendment_block(obs))
            parts.append("")

    gaps = _gaps_block(report)
    if gaps:
        parts.extend([_RULE, gaps, ""])

    if narrative:
        safe = _gate(narrative)
        if safe:
            parts.append("PLAIN-LANGUAGE SUMMARY (generated)\n" + _wrap(safe))
            parts.append("")

    parts.append(_footer())
    return "\n".join(parts)


def to_json(report: ReconciliationReport, narrative: str | None = None) -> dict:
    coverage = report.coverage
    return {
        "tool": report.tool,
        "version": report.version,
        "generated": report.generated,
        "scope_note": report.scope_note,
        "sources": [
            {"source_id": s.source_id, "name": s.name, "url": s.url,
             "retrieved_date": s.retrieved_date, "snapshot_label": s.snapshot_label}
            for s in report.sources
        ],
        # The rate and the words explaining it travel together here exactly as they do in the
        # text report. A consumer of this JSON cannot pick up the number alone.
        "match_rate": None if coverage is None else {
            "independent_records_examined": coverage.independent_records_examined,
            "independent_records_matched": coverage.independent_records_matched,
            "matched_percent": coverage.matched_percent,
            "unmatched_percent": coverage.unmatched_percent,
            "scope_note": coverage.scope_note,
            "method_note": coverage.method_note,
            "interpretation": coverage.interpretation,
            "benchmark_note": coverage.benchmark_note,
            "per_company_breakdown": None,
            "per_company_breakdown_note": (
                "Not produced, by design. A per-company match rate would be read as 'this "
                "company is missing N% of its incidents', which this number cannot support: "
                "it is dominated by whether a fleet is consumer-owned, by fleet size, and by "
                "operating geography."
            ),
        },
        "findings": [
            {
                "kind": f.kind,
                "independent_record": {
                    "population": f.independent_record.population_id,
                    "record_ref": f.independent_record.record_ref,
                    "entity_name": f.independent_record.entity_name,
                    "incident_date": f.independent_record.incident_date,
                    "filed_date": f.independent_record.filed_date,
                    "vin_prefix": f.independent_record.vin_prefix,
                    "injuries_reported": f.independent_record.injuries_reported,
                    "deaths_reported": f.independent_record.deaths_reported,
                    "components": f.independent_record.components,
                    "source_url": f.independent_record.source_url,
                    "summary_quoted": f.independent_record.summary_quoted,
                    "summary_quoted_note": (
                        "The complainant's own words, republished verbatim and attributed to "
                        "them. Not this tool's characterisation of any event."
                    ),
                },
                "filing": None if f.filing is None else {
                    "report_id": f.filing.report_id,
                    "report_version": f.filing.report_version,
                    "reporting_entity": f.filing.reporting_entity,
                    "report_type": f.filing.report_type,
                    "incident_date": f.filing.incident_date,
                    "city": f.filing.city,
                    "state": f.filing.state,
                    "vin_prefix": f.filing.vin_prefix,
                    "highest_injury_severity": f.filing.highest_injury_severity,
                    "submission_date": f.filing.submission_date,
                },
                "match": None if f.match is None else {
                    "method": f.match.match_method,
                    "score": f.match.match_score,
                    "confidence": f.match.match_confidence,
                    "date_delta_months": f.match.date_delta_months,
                    "gate_note": f.match.gate_note,
                },
                "differences": [
                    {"field_label": d.field_label,
                     "filing_field_name": d.filing_field_name,
                     "filing_value": d.filing_value,
                     "independent_field_name": d.independent_field_name,
                     "independent_value": d.independent_value}
                    for d in f.differences
                ],
                "innocent_explanations": list(f.innocent_explanations),
                "caveat": disclaimers.get_caveat(f.caveat_key),
            }
            for f in report.findings
        ],
        "amendments": {
            "note": (
                "A filing compared against a LATER VERSION OF ITSELF. Not a cross-source "
                "check, not independent corroboration, and excluded from the match rate."
            ),
            "observations": [
                {
                    "report_id": a.report_id,
                    "reporting_entity": a.reporting_entity,
                    "from_version": a.from_version,
                    "to_version": a.to_version,
                    "from_submission_date": a.from_submission_date,
                    "to_submission_date": a.to_submission_date,
                    "changed_fields": list(a.changed_fields),
                    "caveat": disclaimers.get_caveat(a.caveat_key),
                }
                for a in report.amendments
            ],
        },
        "known_gaps": list(report.known_gaps),
        "disclaimers": {
            "scope": disclaimers.SCOPE_DISCLAIMER,
            "what_it_is": disclaimers.HEADER_WHAT_IT_IS,
            "what_it_is_not": disclaimers.HEADER_WHAT_IT_IS_NOT,
            "footer": disclaimers.FOOTER,
            "absence": disclaimers.ABSENCE,
        },
        "narrative": _gate(narrative) if narrative else None,
        "compared_fields": list(config.COMPARED_FIELDS),
    }
