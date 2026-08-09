"""disclaimers.py -- curated caveat/disclaimer constants, force-attached by the renderer.

These are the human-reviewed framing strings. A finding block cannot render without its
caveat, and a match rate cannot render without its interpretation.

**They are deliberately NOT scanned by framing_guard.** Several of them name concealment,
intent, and wrongdoing in order to DISAVOW them ("this is not evidence of concealment"), so
they would trip the guard's lemma layer by design -- the same boundary tie-check drew, for the
same reason. Their correctness is guaranteed by the exact-content tests in
tests/test_disclaimers.py instead.
"""
from __future__ import annotations

# --- Standing disclaimers -----------------------------------------------------

SCOPE_DISCLAIMER = (
    "filingcheck reports checkable differences between a public incident filing and "
    "independent public records. It does not determine whether a filing was correct, "
    "complete, or made in good faith, and it produces no score or rate for any company. A "
    "difference is a starting point for a qualified human to check both sources; it is not a "
    "finding of wrongdoing."
)

HEADER_WHAT_IT_IS = (
    "WHAT THIS REPORT IS\n"
    "  A list of checkable differences between NHTSA Standing General Order incident\n"
    "  filings and independent public records that the reporting party does not control.\n"
    "  Every difference cites both documents by their public identifiers, so any reader can\n"
    "  retrieve both and check the comparison independently."
)

HEADER_WHAT_IT_IS_NOT = (
    "WHAT THIS REPORT IS NOT\n"
    "  It is not a determination that any filing was incomplete, incorrect, or improper, and\n"
    "  it is not a statement about any company's honesty, intent, or compliance. It produces\n"
    "  no per-company score and no per-company match rate, by design. Two public records\n"
    "  describing the same event routinely differ for reasons that involve no fault on\n"
    "  anyone's part -- see the explanations attached to every difference below."
)

FOOTER = (
    "This report compares documents, not companies. It is decision-support for a reader who\n"
    "will retrieve and read both cited sources, not a standalone judgment. Differences\n"
    "between independently-maintained public records are normal and expected; this tool\n"
    "surfaces them for checking and does not explain why any particular one exists."
)

# --- The innocent explanations, attached to every cross-source finding ---------
# Ordered most-common-first. These are not hedges: in a reconciliation between two
# populations built for different purposes, these account for the overwhelming majority of
# differences, and a reader who forgets that will misread the report.

INNOCENT_EXPLANATIONS = (
    "Reporting thresholds differ. Each source defines a reportable event differently, so an "
    "event that belongs in one population may correctly never appear in the other.",
    "Timing differs. Filings, amendments, and consumer complaints are submitted on different "
    "clocks; a record present in one source may simply not have been submitted to the other "
    "yet, or may fall outside this snapshot's date window.",
    "Either source may contain an error. Consumer complaints are unverified self-reports, and "
    "filing data is published by NHTSA as submitted and may be incomplete or unverified.",
    "Duplicate or split records. One real event can produce several records in one source and "
    "a single record in another, in either direction.",
    "The two sources capture different things. They are collected by different processes, from "
    "different people, for different purposes, and are not designed to agree field-for-field.",
    "The record linkage itself may be wrong. A match is a candidate, not an established fact "
    "that the two records describe the same event.",
)

# --- Per-block caveats, keyed ------------------------------------------------

FINDING_NOTE = (
    "Note: This records a difference between two public documents. It is not a determination "
    "that either document is wrong, that anything was concealed or left out improperly, or "
    "that any company acted with intent. Both records are cited above so the comparison can be "
    "checked directly against the sources. Differences between independently-maintained public "
    "records are expected and usually have an ordinary explanation."
)

UNMATCHED_NOTE = (
    "Note: This independent record was not matched to any filing in this snapshot. The most "
    "likely reasons, by a wide margin, are that the event is not reportable under the "
    "Standing General Order, that the two sources use different reporting thresholds, or that "
    "the matching method used here is too strict to link records that do describe the same "
    "event. An unmatched record is not evidence that a filing is missing, and this tool does "
    "not claim it is."
)

AMENDMENT_NOTE = (
    "Note: This compares a filing against a LATER VERSION OF ITSELF. It is not a cross-source "
    "check, it is not independent corroboration of anything, and it is excluded from the match "
    "rate. A filer amending its own filing is the reporting system working as intended: new "
    "information arrives, and the record is corrected. That is the ordinary reason these "
    "fields differ between versions, and nothing here indicates otherwise."
)

LOW_CONFIDENCE = (
    "Low-confidence linkage: these two records were linked by entity name and date proximity, "
    "not by a shared identifier. Verify that both records describe the same event before "
    "relying on any difference listed here."
)

ABSENCE = (
    "No checkable differences were produced for this scope. This is not a confirmation that "
    "the filings are complete or accurate. It means the independent populations searched here, "
    "on this snapshot date, produced no record that this method could link to a filing and "
    "compare. Coverage of both populations is incomplete."
)

# --- The match rate: the interpretation is inseparable from the number ---------
# MatchRateDisclosure refuses to be constructed without this text.

MATCH_RATE_INTERPRETATION = (
    "WHAT THIS RATE MEANS -- read before quoting it.\n"
    "  This is the share of independent public records that this tool's method could link to\n"
    "  a filing. It measures THIS METHOD's reach across two populations built for different\n"
    "  purposes. It is not a completeness measure, not an error rate, and not a measure of\n"
    "  any company's reporting.\n"
    "  A LOW match rate is the expected result, and it was expected before this tool was\n"
    "  written. The largest single driver is that the two populations barely overlap by\n"
    "  construction: consumer complaints are filed by vehicle owners, and a driverless fleet\n"
    "  has no owner to file one. Strict linkage rules, different reporting thresholds, and\n"
    "  different date windows account for most of the rest.\n"
    "  The rate is reported for the whole run and is never broken out by company. Per-company\n"
    "  rates would be read as 'this company is missing N% of its incidents' -- which this\n"
    "  number cannot support, since it is dominated by fleet ownership model, fleet size, and\n"
    "  operating geography rather than by anything about a company's reporting."
)

MATCH_RATE_BENCHMARK = (
    "For calibration: EMIR's dual-sided trade reconciliation -- a mandatory regime, in a far "
    "more structured domain, with both sides legally required to report the same transaction "
    "-- still left up to 55% of trades unreconciled after four years. Cross-source "
    "reconciliation is genuinely messy everywhere it has been attempted. A high non-match rate "
    "here is a property of the problem, not a defect in this tool or in any filer."
)

# --- Known coverage gaps, stated up front rather than discovered by a user -----

KNOWN_GAPS = (
    "Police-reported crash data (Berkeley TIMS / California SWITRS) is NOT included. It is the "
    "population academic ADS crash-rate research uses, and it would be the strongest "
    "independent source available -- but it requires an account, which puts it outside this "
    "tool's public-data-only constraint.",
    "California DMV OL 316 autonomous vehicle collision reports are NOT included. As of this "
    "snapshot, the DMV's public listing of those reports is no longer reachable, and the "
    "collision-reports link on the DMV's autonomous vehicles page now points to a dashboard "
    "built from NHTSA SGO data -- the same population being checked here, so it would not be "
    "an independent source.",
    "Court filings are NOT included in this version. CourtListener's public API is usable and "
    "this is a deferred addition, not a limitation of principle.",
    "News coverage is NOT included in this version. It is the noisiest population to match "
    "and was deferred rather than done poorly.",
    "Only NHTSA consumer complaints serve as the independent population in this version. That "
    "single-source scope is the most important limit on everything reported here.",
)

CAVEATS = {
    "FINDING_NOTE": FINDING_NOTE,
    "UNMATCHED_NOTE": UNMATCHED_NOTE,
    "AMENDMENT_NOTE": AMENDMENT_NOTE,
    "LOW_CONFIDENCE": LOW_CONFIDENCE,
    "ABSENCE": ABSENCE,
}


def get_caveat(caveat_key: str | None) -> str:
    if caveat_key is None:
        return ""
    if caveat_key not in CAVEATS:
        raise KeyError(f"Unknown caveat_key: {caveat_key!r}")
    return CAVEATS[caveat_key]
