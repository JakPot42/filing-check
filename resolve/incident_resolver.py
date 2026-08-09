"""incident_resolver.py -- cross-source record linkage.

Fifth deployment of the same three-band fuzzy-match engine first built for GhostTrace
(jurisdiction-conflict gate for shell-company ownership chains), then adapted for tech-scanner
(institution names), PatientFusion (DOB gate) and entity-graph (cross-project entity merge).

`normalize_name` and `similarity` are carried over unchanged. What is specific to this
deployment is the unit and the gate:

  - **The unit is an incident, not an entity.** Two records are linked when they plausibly
    describe the SAME EVENT, across a filing population and an independent population that
    share almost no schema.

  - **The hard gate is entity + vehicle configuration + month.** Every prior deployment
    carried a gate that no similarity score may override -- GhostTrace's jurisdiction
    conflict, PatientFusion's date of birth. Here two records may never be linked across
    different reporting entities, without a shared VIN prefix, or more than
    INCIDENT_MONTH_TOLERANCE months apart, regardless of how similar everything else looks.
    Month rather than day because that is the precision NHTSA publishes for a filing.

**Why the gate is strict, and why the ambiguous band stays unlinked:** in the earlier
deployments a missed merge was recoverable and a wrong merge poisoned a graph. Here a wrong
link is worse than that -- it manufactures a difference between two documents that describe
unrelated events, and attaches it to a named company. A missed link inflates the non-match
rate, which is a disclosed, expected, and honest outcome. Those costs are not symmetric, so
this resolver is deliberately biased toward not linking.
"""
from __future__ import annotations

import datetime
from difflib import SequenceMatcher

import config
from models import Match

# Corporate suffixes stripped before comparison. The two populations write the same company
# differently: the SGO CSV says "Tesla, Inc." and a complaint says "Tesla, Inc." but the same
# filer appears as "Toyota Motor Engineering & Manufacturing" in one and "Toyota Motor
# Corporation" in the other.
_SUFFIXES = {"inc", "llc", "ltd", "corp", "corporation", "company", "co", "lp", "llp", "plc",
             "gmbh", "ag", "sa", "nv", "bv", "holdings", "group", "of", "america",
             "north", "north america", "usa", "us", "motors", "motor"}

# Curated aliases checked BEFORE fuzzy scoring, for pairs that share no normalized tokens.
# Same mechanism entity-graph needed for "GE Power" -> "General Electric Company"; the entries
# here were derived from the reporting-entity and manufacturer strings that actually appear in
# the two populations, not invented.
KNOWN_ALIASES = {
    "waymo": "Waymo LLC",
    "google": "Waymo LLC",
    "tesla": "Tesla, Inc.",
    "general": "General Motors, LLC",
    "gm": "General Motors, LLC",
    "cruise": "General Motors, LLC",
    "zoox": "Zoox, Inc.",
    "ford": "Ford Motor Company",
    "honda american honda": "Honda (American Honda Motor Co.)",
    "hyundai": "Hyundai Motor America",
    "kia": "Kia America, Inc.",
    "subaru": "Subaru of America, Inc.",
    "toyota engineering manufacturing": "Toyota Motor Engineering & Manufacturing",
    "bmw": "BMW of North America, LLC",
}

# Full-date formats (complaints). SGO filings do not use any of these -- see parse_month.
_DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y")

# The SGO CSV publishes the incident date as a month only: "APR-2026". NHTSA does not publish
# the day, so month is the finest precision the filing side of any comparison can have.
_MONTH_FORMATS = ("%b-%Y", "%B-%Y", "%Y-%m", "%m/%Y")


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, drop leading 'the' and corporate suffixes."""
    cleaned = "".join(ch if ch.isalnum() or ch == " " else " " for ch in (name or "").lower())
    tokens = cleaned.split()
    if tokens and tokens[0] == "the":
        tokens = tokens[1:]
    while tokens and tokens[-1] in _SUFFIXES:
        tokens = tokens[:-1]
    tokens = [t for t in tokens if t not in _SUFFIXES]
    return " ".join(tokens)


def similarity(a: str, b: str) -> float:
    """0-100 similarity between two normalized names.

    Max of three measures so word order and partial overlap do not defeat the match: direct
    ratio, token-sort ratio, and token-set Jaccard overlap. Unchanged from every prior
    deployment."""
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 100.0
    direct = SequenceMatcher(None, na, nb).ratio()
    ta, tb = na.split(), nb.split()
    token_sort = SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    sa, sb = set(ta), set(tb)
    token_set = len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0
    return max(direct, token_sort, token_set) * 100


def resolve_known_alias(name: str) -> str | None:
    """Curated alias lookup, run BEFORE fuzzy scoring."""
    return KNOWN_ALIASES.get(normalize_name(name))


def canonical_entity(name: str) -> str:
    return resolve_known_alias(name) or (name or "").strip()


def parse_date(value: str) -> datetime.date | None:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime((value or "").strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def parse_month(value: str) -> tuple | None:
    """(year, month) from either a month-only value ("APR-2026") or a full date.

    Handles both populations with one function because the comparison between them can only
    ever happen at month precision: the filing side has nothing finer."""
    raw = (value or "").strip()
    if not raw:
        return None
    for fmt in _MONTH_FORMATS:
        try:
            parsed = datetime.datetime.strptime(raw, fmt)
            return parsed.year, parsed.month
        except (ValueError, TypeError):
            continue
    full = parse_date(raw)
    return (full.year, full.month) if full else None


def month_delta(a: str, b: str) -> int | None:
    """Absolute difference in whole months, or None if either value is unparseable/absent.

    None means "cannot evaluate the gate", and the gate then REFUSES the link. An unknown
    date is never treated as a satisfied constraint."""
    ma, mb = parse_month(a), parse_month(b)
    if ma is None or mb is None:
        return None
    return abs((ma[0] - mb[0]) * 12 + (ma[1] - mb[1]))


def entity_similarity(filing_entity: str, record_entity: str) -> float:
    """Similarity between the two populations' names for the same company, aliases first."""
    a, b = canonical_entity(filing_entity), canonical_entity(record_entity)
    if normalize_name(a) == normalize_name(b):
        return 100.0
    return similarity(a, b)


def passes_gate(filing, record) -> tuple:
    """The hard gate. Returns (passes, note).

    No similarity score anywhere in this module can override it. THREE conditions must hold:

      1. the two records name the same reporting entity;
      2. they share an 11-character VIN prefix -- the same vehicle configuration, year and
         plant. Without it there is no basis to suppose two records describe the same event,
         since manufacturer-plus-month would link any Tesla filing to any Tesla complaint in
         the same month;
      3. their incident months are within tolerance, and both are parseable.

    Note what condition 2 does NOT establish: neither source publishes VIN characters 12-17,
    the serial that identifies an individual vehicle. A shared prefix is a shared
    configuration, not a shared vehicle -- which is why no match from this module is treated
    as high confidence."""
    entity_score = entity_similarity(filing.reporting_entity, record.entity_name)
    if entity_score < config.FUZZY_AUTO_MERGE_THRESHOLD:
        return False, (f"different reporting entity ({filing.reporting_entity!r} vs "
                       f"{record.entity_name!r}, {int(round(entity_score))}/100)")

    filing_vin = (filing.vin_prefix or "").strip().upper()
    record_vin = (record.vin_prefix or "").strip().upper()
    if config.REQUIRE_VIN_PREFIX_FOR_LINKAGE:
        if not filing_vin or not record_vin:
            return False, "no VIN prefix published in one of the two records"
        if filing_vin != record_vin:
            return False, (f"different vehicle configuration (VIN prefix {filing_vin} vs "
                           f"{record_vin})")

    delta = month_delta(filing.incident_date, record.incident_date)
    if delta is None:
        return False, "incident date missing or unparseable in one of the two records"
    if delta > config.INCIDENT_MONTH_TOLERANCE:
        return False, (f"incident months {delta} apart, beyond the "
                       f"{config.INCIDENT_MONTH_TOLERANCE}-month tolerance")

    return True, (f"same reporting entity; shared VIN prefix {filing_vin} (a vehicle "
                  f"configuration, not an individual vehicle); incident months {delta} apart")


def link(filing, record) -> Match | None:
    """Produce a candidate linkage between one filing and one independent record, or None.

    Every returned Match is a CANDIDATE for human verification -- the candidates-only posture
    inherited from GhostTrace's ofac_checker through tie-check. In this version NO method is
    high confidence: the strongest key either source publishes is a VIN prefix, which is a
    vehicle configuration rather than an individual vehicle (see passes_gate)."""
    passes, note = passes_gate(filing, record)
    if not passes:
        return None

    delta = month_delta(filing.incident_date, record.incident_date) or 0
    method = "VIN_PREFIX_MONTH"
    score = int(round(entity_similarity(filing.reporting_entity, record.entity_name)))
    confidence = "HIGH" if method in config.HIGH_CONFIDENCE_METHODS else "LOW"

    return Match(
        filing_report_id=filing.report_id,
        filing_version=filing.report_version,
        independent_record_ref=record.record_ref,
        match_method=method,
        match_score=score,
        match_confidence=confidence,
        date_delta_months=delta,
        gate_note=note,
    )


def build_index(filings: list) -> dict:
    """Index filings by VIN prefix, then by incident month.

    A full scan is the obvious implementation and it is unusably slow at real scale: 1,181
    independent records against 1,702 filings is two million fuzzy comparisons. The gate is
    what makes an index possible -- since no pair can link without a shared VIN prefix and a
    month inside tolerance, only filings in those buckets can produce a candidate and the rest
    never need to be scored.

    Filings without a parseable month or a VIN prefix are dropped rather than kept: the gate
    refuses them anyway. `passes_gate` remains the single definition of the rule -- this is a
    lookup path to it, not a second copy of it, and every candidate it surfaces is still put
    through `link` (and therefore through the gate) before being accepted.
    """
    index: dict = {}
    for filing in filings:
        month = parse_month(filing.incident_date)
        vin = (filing.vin_prefix or "").strip().upper()
        if month is None or not vin:
            continue
        index.setdefault(vin, {}).setdefault(month, []).append(filing)
    return index


def _months_within(month: tuple, tolerance: int) -> list:
    """Every (year, month) within `tolerance` whole months of `month`."""
    year, mon = month
    out = []
    for offset in range(-tolerance, tolerance + 1):
        total = (year * 12 + (mon - 1)) + offset
        out.append((total // 12, total % 12 + 1))
    return out


def best_link(record, filings, entity_cache: dict | None = None) -> Match | None:
    """Best candidate linkage for one independent record, or None if nothing passes the gate.

    Accepts either a list of filings or an index from `build_index`. Ties are broken by the
    smallest month difference, then by the highest entity score.

    `entity_cache` is accepted for call-site compatibility and is unused: with the VIN prefix
    required, the index is keyed on it directly and no per-entity key sweep is needed."""
    index = filings if isinstance(filings, dict) else build_index(filings)

    record_month = parse_month(record.incident_date)
    record_vin = (record.vin_prefix or "").strip().upper()
    if record_month is None or not record_vin:
        return None      # the gate refuses both cases; do not guess either

    by_month = index.get(record_vin)
    if not by_month:
        return None

    candidates = []
    for month in _months_within(record_month, config.INCIDENT_MONTH_TOLERANCE):
        for filing in by_month.get(month, ()):
            # passes_gate is still the authority: the index narrows the search, it does not
            # decide the outcome.
            match = link(filing, record)
            if match is not None:
                candidates.append(match)

    if not candidates:
        return None
    candidates.sort(key=lambda m: (m.match_confidence != "HIGH", m.date_delta_months,
                                   -m.match_score))
    return candidates[0]
