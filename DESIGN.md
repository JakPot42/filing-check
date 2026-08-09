# filing-check: Public-Data AV/Robotics Incident Reconciliation Monitor
## Architecture, guardrail design, and what the real data turned out to be

> **Build order actually followed (non-negotiable, inherited from claim-check and
> tie-check):** `framing_guard.py` + its tests green FIRST → the structural data-model
> tests green SECOND → the curated caveats and their exact-content tests THIRD → only then any
> matching, comparison, or reporting logic. At the moment the first reconciliation line was
> written, 74 tests were already passing and no code existed that could produce a finding.

> **The one non-negotiable rule everything below serves:** this tool reports **checkable
> differences between a filing and independent public sources**. It never states or implies
> that anything was concealed, omitted improperly, under-reported, or done with intent, and it
> never issues a verdict about a company. A difference has many innocent explanations:
> reporting thresholds, timing, source error, duplicate records, and the plain fact that two
> populations built for different purposes are not designed to agree. Those explanations are
> attached to every single finding, not relegated to a footnote.

---

## PART 0: What the live data actually is (verified, not assumed)

Every claim in this section was checked against the live sources during the build, in the
portfolio's verify-before-building discipline (a lesson from an earlier project that built against an API which had silently died). Three
findings changed the design.

### 0.1 The sources that work

| Source | Status | Role |
|---|---|---|
| NHTSA SGO 2021-01 **ADS** CSV | live, free, no auth, 1,239 rows / 1,200 reports | the filings under examination |
| NHTSA SGO 2021-01 **ADAS** CSV | live, free, no auth, 1,800 rows / 1,702 reports | the filings under examination |
| NHTSA complaints API | live, free, no key | the independent population |

### 0.2 Finding: California DMV's collision-report listing is gone, and the route it now offers is circular

The project spec named police-reported crash data and CA DMV OL 316 collision reports as
independent populations. Neither is usable as specified:

- The DMV's own public listing of OL 316 autonomous-vehicle collision reports **404s**.
- The "See Collision Reports" button on the DMV's autonomous vehicles page now points at **UC
  Berkeley TIMS**, whose AV dashboard is **built from NHTSA SGO data**, the very population
  being checked. Using it would make the reconciliation circular.
- TIMS/SWITRS police-reported crash data requires an **account**, which breaks the
  public-data-only, zero-business-development constraint.

Both are recorded as known coverage gaps in `disclaimers.KNOWN_GAPS`, printed in every report
and asserted by `tests/test_disclaimers.py`.

### 0.3 Finding: filings are published to MONTH precision only

SGO incident dates are published as `APR-2026`. NHTSA does not publish the day. Complaints
carry a full date. **The comparison can therefore only happen at month precision**, which is
the coarser of the two. The original ±3-day linkage tolerance was impossible and was replaced
with a ±1-month tolerance. This is a real limit on the method, stated in the report's own
method note rather than buried here.

### 0.4 Finding: an 11-character VIN prefix is a configuration, not a vehicle

Both populations publish an 11-character VIN prefix, and 165 prefixes are shared between them,
which is what makes any linkage possible at all. But 11 characters is WMI + VDS + check
digit + model year + plant. **Neither source publishes characters 12-17, the serial that
identifies an individual vehicle.** A shared prefix means "same configuration, year and plant",
shared by thousands of vehicles.

Two consequences, both load-bearing:
1. A shared VIN prefix is **required** for a linkage. Without it, "same manufacturer, same
   month" would link any of 1,536 Tesla filings to any Tesla complaint in that month, which is
   not evidence of anything.
2. A shared VIN prefix is **not sufficient for confidence**. `HIGH_CONFIDENCE_METHODS` is
   empty: no linkage in this version is high confidence, and every match is labelled a
   candidate for human verification.

### 0.5 Finding: the complaints database has its own model vocabulary

The SGO CSV says `Model Y`; the complaints API answers only to `MODEL Y (All Variants)` and
returns a **silent zero-result** for anything else. A silent zero is the dangerous failure mode
here: it is indistinguishable from "no independent records exist", which would make the
filings look better corroborated than they are. Model names are therefore resolved against
NHTSA's own `/products/vehicle/models` endpoint using the portfolio's fuzzy resolver, and
`ConfigResolution.resolved` records whether each configuration was queryable at all. In the
August 2026 snapshot, **140 of 176 configurations were queryable**; the report states the
36 that were not, because for those the independent population is *absent*, not *empty*.

---

## PART 1: The data model, and the proof a verdict cannot be represented

The atomic unit is a **difference between two documents**, never an attribute of a company.

Five structural guarantees, each proven by `tests/test_models_no_verdict.py` (a field scan plus a
decision-module purity check, both patterns proven in earlier projects):

1. **Nowhere to store a verdict.** No model has a field whose name contains concealment,
   intent, deliberateness, negligence, wrongdoing, violation, or fault. A `Finding` holds two
   cited records and the fields on which they differ, the test pins its exact field set.
2. **No company-level score, and no company-level match rate.** `MatchRateDisclosure` has no
   field that could name a company; a test scans for `entity`, `company`, `filer`, `operator`,
   `manufacturer`, `make`, `brand`.
3. **Amendments are a different type.** `AmendmentObservation` is not a `Finding` and has no
   `FindingKind`, so a self-comparison structurally cannot enter the cross-source findings or
   the match rate.
4. **The report exposes no int/float field.** Counts live only on the coverage object.
5. **A match rate cannot exist without its interpretation.** `MatchRateDisclosure.__post_init__`
   raises on empty `interpretation`, so no code path can emit a bare percentage.

The one score in the model is `Match.match_score`, and its location is deliberate and tested:
it scores the **linkage between two documents**, not a company, the same posture as
tie-check's per-tie score.

---

## PART 2: How the match rate is disclosed

*"How that rate is disclosed rather than smoothed over is itself part of the build."*

The disclosure is structural, not editorial:

- **The rate and its meaning are one object.** `coverage.build()` attaches
  `MATCH_RATE_INTERPRETATION` and `MATCH_RATE_BENCHMARK` at construction, so the text report,
  the JSON export, and any future consumer receive them inseparably.
- **The rate appears BEFORE the findings**, in both the text report and this document. A
  reader who meets a list of differences first has already formed an impression that a
  coverage statistic at the end has to argue against.
- **The low result is pre-authorised in the text itself**: *"A LOW match rate is the expected
  result, and it was expected before this tool was written."* Followed by the reason: the two
  populations barely overlap by construction, since a driverless fleet has no owner to file a
  consumer complaint.
- **The EMIR benchmark travels with it**: dual-sided trade reconciliation, mandatory, in a far
  more structured domain, still left up to 55% of trades unreconciled after four years.
- **`coverage.py` is proven blind to amendments and to companies**: a source scan asserts its
  code never mentions amendments, and a signature scan asserts neither of its functions takes
  an entity.
- **An empty population yields `None`, never 0.0% or 100%.** A rate over nothing is not a
  result, and rendering one would invent it.

### Why there is no per-company match rate

Refused deliberately, and recorded so it is not "fixed" later. A per-company rate reads as
*"this company is missing N% of its incidents."* It is not that: it is dominated by whether a
fleet is consumer-owned, by fleet size, and by operating geography. Publishing it per company
would convert a coverage statistic about *this tool's method* into a scoreboard about
corporate honesty, the exact inference this project exists to avoid. Refusing it is the same
credibility wedge tie-check makes by refusing a person-level score.

---

## PART 3: Results of the first real run (snapshot 2026-08-09)

| | ADS filings | ADAS (Level 2) filings |
|---|---|---|
| Independent records examined | 1,181 | 1,181 |
| Linked to a filing | **0** | **44** |
| Match rate | **0.0%** | **3.7%** |
| Non-match rate | **100%** | **96.3%** |
| Field differences found | 0 | 1 |
| Amendment transitions observed | 39 | 98 |

**The 96.3%-100% non-match rate is the headline result, and it is the expected one.** It is
far above the 55% EMIR benchmark, for a reason visible in the data: Waymo's fleet is the Jaguar
I-PACE 2024 (947 filings), for which 18 consumer complaints exist and **none** is a crash. A
driverless fleet has no owner to file a consumer complaint. The ADS result is 0% not because
filings are missing but because **the two populations barely intersect by construction**.

**The substantive methodological result.** The question worth asking of a tool like this is
whether a filed, well-formed, internally consistent report that still does not line up with
independent sources is findable in public data at all. What this build establishes is narrower
and more useful than a yes/no: with the populations that are *actually* public and *actually*
reachable without an account, **cross-source corroboration of automated-vehicle incident
filings is close to unavailable in the driverless case**, which is precisely where autonomy,
and therefore interest in independent corroboration, is highest. The one population that would
work (police crash data) is behind an account, and the regulator's own route to independent
collision reports now leads back to the filings themselves (Part 0.2).

**The one cross-source difference found, a demonstration case, not a headline finding.** SGO
report 13781-12029 v2 (Tesla, Inc., Hesperia CA, Oct-2025) records *"Property Damage. No
Injured Reported"*; NHTSA complaint ODI 11693937, same manufacturer, same VIN configuration,
same month, records 1 injury. It is labelled **LOW confidence**, as every linkage this tool
currently produces is: a shared VIN prefix is a configuration rather than an identified
vehicle, so **the two records may describe entirely different events**. The complaint is an
unverified self-report. This is a single case from a first run, has not been independently
checked, and should not be treated as conclusive or as evidence of anything about the named
company's reporting. It is included as an example of what the method emits. Both documents are
cited so any reader can retrieve them and judge for themselves.

**What this run does not show.** It is not evidence that any filing is missing, incomplete, or
wrong. A 96.3% non-match rate measures this method's reach across two populations that were
never designed to agree, nothing more.

---

## PART 4: Where the constraint is in tension with usefulness

**#1: "Unmatched" read as "unreported."** The central risk. An unmatched independent record
looks like a missing filing and is almost never one. Resolution, layered: the finding kind is
`UNMATCHED_INDEPENDENT_RECORD` (never `MISSING_FILING`); `UNMATCHED_NOTE` states *"not evidence
that a filing is missing, and this tool does not claim it is"* and offers **the method's own
strictness first** among the explanations; and the match rate leads the report so the scale of
non-matching is context, not a surprise.

**#2: A per-company rate would be the most requested feature and the most harmful.** Refused
structurally (Part 2). State it as a feature.

**#3: Indeterminate values manufacturing differences.** "Unknown" is the injury severity on
1,576 of 1,800 Level 2 filings. Treating it as "no injury" would generate false differences at
scale, against named companies. Resolution: a comparison is **skipped entirely** whenever
either side is indeterminate; tested per-value.

**#4: Wrong links inventing differences.** A wrong link attaches a fabricated discrepancy to a
named company; a missed link only lowers a disclosed rate. Those costs are not symmetric, so
the resolver is biased toward not linking: a three-part hard gate (entity + VIN prefix + month)
that no similarity score can override, and no high-confidence tier at all.

**#5: Amendments over-read as admissions.** A filer amending its own filing is the reporting
system working as designed. Resolution: a separate type, a separate report section, exclusion
from the match rate, `AMENDMENT_NOTE` stating all three, and **no word-level narrative diff**.
Diffing narrative prose invites precisely the inference that what was added should have been
there the first time. Only *which fields changed* is reported.

**#6: The tool republishing a complainant's accusation as its own.** Complaint summaries are
unverified self-reports that sometimes allege a cover-up. Resolution: `summary_quoted` is
republished verbatim, attributed, carried only in the JSON export with an attribution note, and
**never routed through the framing guard**: the guard governs what this tool writes, not what
a public record says. Tested.

**#7: Naming real companies at all.** Decided deliberately: the subjects are corporations, not
people; every input is a government record; and the project's purpose is producing real
evidence, which a synthetic demo cannot do. The reputation safety is discharged structurally
(guards, no-verdict model, mandatory caveats) rather than by hiding the data.

**#8: Silent zero-results overstating corroboration.** See Part 0.5. Resolution:
`ConfigResolution.resolved`, and a report that distinguishes absent from empty.

---

## PART 5: Layout

```
av_incident_reconciliation/
├── framing_guard.py          OUTPUT guard -- GREEN FIRST
├── models.py                 the Part 1 dataclasses + structural guarantees
├── disclaimers.py            curated caveats; force-attached; NOT guard-scanned
├── config.py                 sources, thresholds, the gate, compared fields
├── sources/
│   ├── sgo.py                pinned SGO CSV loader; keeps superseded versions
│   └── complaints.py         complaints API + model-vocabulary resolution
├── resolve/
│   └── incident_resolver.py  5th deployment of the resolver; gate + index
├── reconcile/
│   ├── crosscheck.py         tracing direction only: independent -> filings
│   ├── amendments.py         self-comparison, separate type, separate section
│   └── coverage.py           the match rate; blind to amendments and companies
├── report/{templates,render}.py
├── pipeline.py  ·  cli.py  ·  snapshots/
└── tests/                    132 tests
```

**Data flow:** `pinned SGO snapshot -> filings (all versions) -> latest_versions -> trace
independent records INTO them -> findings + matched count`, with `version_groups -> amendment
observations` on a separate path that never reaches `coverage`.

---

## PART 6: Reused lineage

Fifth deployment of the portfolio's `entity_resolver` pattern (GhostTrace → tech-scanner
→ PatientFusion → entity-graph → here). `normalize_name`, `similarity` and the
three-band structure are carried over unchanged; `KNOWN_ALIASES` is reused for names sharing no
tokens (the entity-graph GE-Power lesson: here, `Cruise` → `General Motors, LLC`).

What is specific to this deployment: the unit is an **incident**, not an entity, and the hard
gate is **entity + vehicle configuration + month**, the analogue of GhostTrace's jurisdiction
gate and PatientFusion's DOB gate. The index in `build_index` is a lookup path to that gate,
never a second copy of it: every candidate it surfaces is still put through `passes_gate`
before being accepted. Adding it took the ADAS run from unusably slow to 1.7 seconds, the same
shape as an earlier ray-tracer vectorisation fix in this portfolio.
