"""coverage.py -- build the match rate disclosure.

This module is deliberately narrow, and deliberately blind to two things.

**It never sees amendments.** `build()` takes only the independent records examined and the
number of them that were linked. There is no parameter through which an amendment could enter
the rate, which is what keeps the exclusion structural rather than a matter of remembering.
tests/test_coverage_disclosure.py asserts this module's source never mentions amendments.

**It never sees a company.** The rate is computed over a whole run. There is no per-entity
breakdown here and no way to ask for one -- see models.MatchRateDisclosure, which has no field
to hold a company, and DESIGN.md Part 4 #2 for why that refusal is deliberate.

The disclosure object refuses to exist without its interpretation text, so there is no code
path in this project that can emit a bare percentage.
"""
from __future__ import annotations

import disclaimers
from models import MatchRateDisclosure


def build(records_examined: int, records_matched: int, scope_note: str,
          method_note: str) -> MatchRateDisclosure:
    """Assemble the rate together with the words that make it readable.

    The interpretation and benchmark are attached here, not by the renderer, so that any
    consumer of this object -- text report, JSON export, or a future caller this project does
    not know about -- receives them inseparably from the number.
    """
    return MatchRateDisclosure(
        independent_records_examined=records_examined,
        independent_records_matched=records_matched,
        scope_note=scope_note,
        method_note=method_note,
        interpretation=disclaimers.MATCH_RATE_INTERPRETATION,
        benchmark_note=disclaimers.MATCH_RATE_BENCHMARK,
    )


def method_note(month_tolerance: int, high_confidence_methods: tuple,
                configurations_resolved: int, configurations_total: int) -> str:
    """A plain statement of how the rate was produced, including what limits it.

    Written to be read alongside the number by someone deciding whether to trust it, so it
    leads with the method's own strictness rather than with the result.
    """
    unresolved = configurations_total - configurations_resolved
    lines = [
        "HOW THIS RATE WAS PRODUCED",
        "  Direction: every independent record was traced INTO the filings. The reverse",
        "  direction is not computed -- consumer complaints exist for a small, non-random",
        "  slice of vehicles, so a filing without a complaint is the normal case and means",
        "  nothing.",
        "  Linkage gate: same reporting entity, a shared 11-character VIN prefix, and",
        f"  incident months within {month_tolerance} month. A record outside that gate is left",
        "  unmatched no matter how similar it looks. The gate is strict on purpose: a wrong",
        "  link invents a difference against a named company, while a missed link only lowers",
        "  this rate, which is disclosed.",
        "  Month, not day, because that is the precision the filings have: NHTSA publishes the",
        "  SGO incident date as a month only. Complaints carry a full date; the comparison can",
        "  only happen at the coarser of the two.",
        "  NO linkage here is high confidence. Neither source publishes VIN characters 12-17,",
        "  the serial identifying an individual vehicle, so a shared prefix means a shared",
        "  vehicle configuration, year and plant -- not a shared vehicle. Every match is a",
        "  candidate for human verification, not an established fact that two records describe",
        "  the same event.",
        "  Only crash-flagged complaints were treated as eligible, since the filing",
        "  population is a crash-report population.",
        f"  Vehicle configurations: {configurations_resolved} of {configurations_total}",
        "  could be matched to a model name the complaints database recognises.",
    ]
    if unresolved > 0:
        lines.append(
            f"  {unresolved} configuration(s) could not be queried at all, so the independent"
        )
        lines.append(
            "  population for those vehicles is absent rather than empty -- an important"
        )
        lines.append("  difference, and one this rate cannot distinguish.")
    return "\n".join(lines)
