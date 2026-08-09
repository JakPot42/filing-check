"""pipeline.py -- orchestration.

Data flow:
    pinned SGO snapshot -> filings (all versions)
        |-> latest_versions -> trace independent records INTO them -> findings + matched count
        |-> version_groups  -> amendment observations (separate, excluded from the rate)
    pinned complaints snapshot -> independent records
    -> coverage disclosure -> ReconciliationReport
"""
from __future__ import annotations

import config
import disclaimers
from models import ReconciliationReport
from reconcile import amendments as amendments_mod
from reconcile import coverage as coverage_mod
from reconcile import crosscheck
from sources import complaints as complaints_src
from sources import sgo as sgo_src


def run(report_type: str, generated: str, entity_filter: str | None = None) -> ReconciliationReport:
    """Reconcile one filing population against the independent population."""
    records, resolutions, complaints_date = complaints_src.load_snapshot()
    filings_all = sgo_src.load_filings(report_type, retrieved_date=complaints_date)

    if entity_filter:
        needle = entity_filter.strip().lower()
        filings_all = [f for f in filings_all if needle in f.reporting_entity.lower()]
        records = [r for r in records if needle in r.entity_name.lower()]

    current = sgo_src.latest_versions(filings_all)
    findings, matched = crosscheck.trace(records, current)
    observations = amendments_mod.observe(sgo_src.version_groups(filings_all))

    resolved = sum(1 for r in resolutions if r.resolved)
    coverage = coverage_mod.build(
        records_examined=len(records),
        records_matched=matched,
        scope_note=(
            f"{len(current)} current-version {report_type} filings; {len(records)} "
            f"crash-flagged independent records"
        ),
        method_note=coverage_mod.method_note(
            month_tolerance=config.INCIDENT_MONTH_TOLERANCE,
            high_confidence_methods=config.HIGH_CONFIDENCE_METHODS,
            configurations_resolved=resolved,
            configurations_total=len(resolutions),
        ),
    )

    scope = config.MVP_SCOPE + f" -- {report_type} filings"
    if entity_filter:
        scope += f", filtered to reporting entities matching {entity_filter!r}"

    return ReconciliationReport(
        findings=findings,
        amendments=observations,
        coverage=coverage,
        sources=[sgo_src.source_ref(report_type, complaints_date),
                 complaints_src.source_ref(complaints_date)],
        scope_note=scope,
        known_gaps=list(disclaimers.KNOWN_GAPS),
        generated=generated,
        tool=config.TOOL_NAME,
        version=config.VERSION,
    )
