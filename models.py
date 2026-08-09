"""models.py -- the data model, with the no-verdict guarantee enforced structurally.

Written and proven green BEFORE any reconciliation logic exists.

Five guarantees, tested rather than documented (tests/test_models_no_verdict.py):

  1. **There is nowhere to store a verdict about a filer.** No model has a field for
     concealment, intent, deliberateness, negligence, wrongdoing, violation, or fault. A
     Finding holds two cited records and the fields on which they differ -- nothing else.

  2. **No company-level score, and no company-level match rate.** MatchRateDisclosure has no
     reporting-entity field at all: the rate is a property of a reconciliation RUN, never of
     a company. This is the structural expression of a deliberate refusal -- see the note
     below, and DESIGN.md Part 4 #2.

  3. **Amendments are a different type from Findings.** AmendmentObservation is not a Finding
     and cannot be placed in `ReconciliationReport.findings`, so an amendment (a filing
     compared against a LATER VERSION OF ITSELF, not against an independent source) can never
     be counted in the cross-source match rate. A separate type is the enforcement; the
     labelling in the report is only the visible half.

  4. **The report exposes no int/float field.** Counts and rates live on
     MatchRateDisclosure, which carries its own mandatory interpretation text.

  5. **A match rate cannot exist without its interpretation.** MatchRateDisclosure raises on
     construction if `interpretation` is empty. The rate and the words explaining what it
     does and does not mean are one object, so no code path can emit a bare percentage.

**Why there is no per-company match rate, recorded here so it is not "fixed" later:** a
per-company rate reads as "this company is missing N% of its incidents". It is not that. It
is dominated by whether a company's vehicles are consumer-owned (a driverless fleet has no
owner to file a consumer complaint), by fleet size, and by operating geography. Publishing it
per company would convert a coverage statistic about this tool's method into a scoreboard
about corporate honesty -- exactly the inference this project exists to avoid. Refusing it is
the same credibility wedge tie-check makes by refusing a person-level score.

`Match.match_score` is the one score in the model and it is deliberate: it scores the
LINKAGE between two documents (how confidently this complaint refers to this filing), which
is a property of the record pair, not of a company. Same posture as tie-check's per-tie
match_score.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# --- Vocabulary ---------------------------------------------------------------

class FindingKind:
    """The complete vocabulary of cross-source findings. Deliberately small, and deliberately
    without any kind that names concealment, omission, or a failure to report.

    AMENDMENT is NOT here: an amendment is not a cross-source finding, and giving it a
    FindingKind would let it enter the findings list and the match rate."""

    UNMATCHED_INDEPENDENT_RECORD = "UNMATCHED_INDEPENDENT_RECORD"
    FIELD_DIFFERENCE = "FIELD_DIFFERENCE"

    ALL = (UNMATCHED_INDEPENDENT_RECORD, FIELD_DIFFERENCE)


class Population:
    """Which population a record belongs to. FILINGS is the document under examination; every
    other value is an independent population the reporting party does not control."""

    FILINGS = "NHTSA_SGO"                       # the filings -- the document being checked
    NHTSA_COMPLAINTS = "NHTSA_COMPLAINTS"       # independent: consumer-filed


# --- Provenance ---------------------------------------------------------------

@dataclass
class SourceRef:
    """Where a record came from, pinned. Every finding is reproducible from these."""
    source_id: str
    name: str
    url: str
    retrieved_date: str
    snapshot_label: str = ""


# --- Records ------------------------------------------------------------------

@dataclass
class FilingRecord:
    """One SGO incident report, at one version. Field names track NHTSA's own schema so a
    reader can find each value in the published CSV; values are republished, never rewritten.

    `declared_data_availability` and `declared_sources` are the filing's OWN statements about
    what data exists and what prompted it. They are descriptive context, never a finding: that
    a filing indicates video is available says nothing about the filing's contents."""
    report_id: str
    report_version: str
    reporting_entity: str
    report_type: str                       # "ADS" | "ADAS"
    submission_date: str = ""
    incident_date: str = ""
    incident_time: str = ""
    city: str = ""
    state: str = ""
    latitude: str = ""
    longitude: str = ""
    vin_prefix: str = ""
    make: str = ""
    model: str = ""
    model_year: str = ""
    highest_injury_severity: str = ""      # NHTSA's own field: "Highest Injury Severity Alleged"
    airbags_deployed: str = ""
    vehicle_towed: str = ""
    investigating_agency: str = ""
    narrative: str = ""
    narrative_cbi: str = ""                # the filing's own confidential-business-info flag
    declared_data_availability: list = field(default_factory=list)
    declared_sources: list = field(default_factory=list)
    source: SourceRef | None = None


@dataclass
class IndependentRecord:
    """One record from a population the reporting party does not control.

    `summary_quoted` is the source's own text, republished verbatim and attributed. It may
    contain a complainant's own allegations; it is never passed through framing_guard (see
    that module's docstring) and never restated as this tool's own words."""
    population_id: str
    record_ref: str                        # e.g. NHTSA ODI number
    entity_name: str                       # as written by the source
    incident_date: str = ""
    filed_date: str = ""
    city: str = ""
    state: str = ""
    vin_prefix: str = ""
    is_crash: bool = False
    injuries_reported: int | None = None
    deaths_reported: int | None = None
    components: str = ""
    summary_quoted: str = ""
    source_url: str = ""
    source: SourceRef | None = None


# --- Linkage ------------------------------------------------------------------

@dataclass
class Match:
    """A candidate linkage between one independent record and one filing.

    `match_score` scores the RECORD PAIR, not a company (see module docstring). Every match is
    a candidate for human verification -- the candidates-only posture inherited from
    GhostTrace's ofac_checker through tie-check."""
    filing_report_id: str
    filing_version: str
    independent_record_ref: str
    match_method: str                      # "VIN_PREFIX_MONTH"
    match_score: int                       # 0-100, linkage confidence between two documents
    match_confidence: str                  # "HIGH" | "LOW" (no method is HIGH in this version)
    date_delta_months: int = 0
    gate_note: str = ""                    # which hard gate admitted this pair


@dataclass
class FieldDifference:
    """One field on which a matched pair of records differs. Both values are republished as
    written by their sources. No severity, no weight, no ranking -- a difference is a
    difference, and which ones matter is the reader's judgment, not this tool's."""
    field_label: str
    filing_value: str
    independent_value: str
    filing_field_name: str = ""            # the literal NHTSA CSV column, for checkability
    independent_field_name: str = ""


# --- Findings -----------------------------------------------------------------

@dataclass
class Finding:
    """One checkable difference between a filing and an independent public record.

    Holds the two records, the linkage, and the fields that differ. There is no field for what
    the difference means, why it exists, or who is responsible -- those do not exist in this
    model, by design. `innocent_explanations` is force-attached from disclaimers.py and is the
    only interpretation the report carries."""
    kind: str                              # FindingKind.*
    independent_record: IndependentRecord
    filing: FilingRecord | None = None
    match: Match | None = None
    differences: list = field(default_factory=list)     # list[FieldDifference]
    innocent_explanations: list = field(default_factory=list)
    caveat_key: str = "FINDING_NOTE"


@dataclass
class AmendmentObservation:
    """A filing compared against a LATER VERSION OF ITSELF.

    A deliberately separate type from Finding: this is not a cross-source check, it is not an
    independent corroboration, and it must never enter the match rate. A filer amending its
    own filing is the reporting system working as designed -- and is the single most common
    innocent explanation for the fields listed here having changed."""
    report_id: str
    reporting_entity: str
    from_version: str
    to_version: str
    from_submission_date: str = ""
    to_submission_date: str = ""
    changed_fields: list = field(default_factory=list)
    caveat_key: str = "AMENDMENT_NOTE"


# --- Coverage disclosure ------------------------------------------------------

@dataclass
class MatchRateDisclosure:
    """The match rate, inseparable from what it means.

    Deliberately has NO reporting-entity field: the rate describes a reconciliation RUN and
    this tool's method, never a company (module docstring, guarantee 2).

    Raises on construction if `interpretation` is empty, so no code path can emit a bare
    percentage. A high non-match rate is the EXPECTED result -- EMIR's dual-sided trade
    reconciliation, a mandatory regime in a far more structured domain, still left up to 55%
    of trades unreconciled after four years -- and `benchmark_note` carries that comparison
    with the rate wherever it appears."""
    independent_records_examined: int
    independent_records_matched: int
    scope_note: str
    method_note: str
    interpretation: str
    benchmark_note: str = ""

    def __post_init__(self) -> None:
        if not (self.interpretation or "").strip():
            raise ValueError(
                "MatchRateDisclosure requires interpretation text: a match rate may never be "
                "emitted without the words explaining what it does and does not mean."
            )
        if self.independent_records_examined < 0 or self.independent_records_matched < 0:
            raise ValueError("record counts may not be negative")
        if self.independent_records_matched > self.independent_records_examined:
            raise ValueError("matched records may not exceed records examined")

    @property
    def matched_percent(self) -> float | None:
        """Percent of independent records matched to a filing, or None when nothing was
        examined. None -- never 0.0 or 100.0 -- because a rate over an empty population is not
        a result, and rendering it as a number would invent one."""
        if self.independent_records_examined == 0:
            return None
        return round(100.0 * self.independent_records_matched
                     / self.independent_records_examined, 1)

    @property
    def unmatched_percent(self) -> float | None:
        matched = self.matched_percent
        return None if matched is None else round(100.0 - matched, 1)


# --- Report -------------------------------------------------------------------

@dataclass
class ReconciliationReport:
    """The whole product: cited findings, separately-labelled amendment observations, and the
    coverage disclosure. Exposes no int/float field of its own -- every count lives on the
    coverage object that carries its own interpretation."""
    findings: list = field(default_factory=list)          # list[Finding]
    amendments: list = field(default_factory=list)        # list[AmendmentObservation]
    coverage: MatchRateDisclosure | None = None
    sources: list = field(default_factory=list)           # list[SourceRef]
    scope_note: str = ""
    known_gaps: list = field(default_factory=list)
    generated: str = ""
    tool: str = ""
    version: str = ""
