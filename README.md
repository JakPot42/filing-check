# filing-check

**Checkable differences between public vehicle-incident filings and independent public records. Never a verdict about a company.**

`filing-check` (CLI: `filingcheck`) reconciles NHTSA Standing General Order incident filings
against independent public records that the reporting party does not control, and reports the
places where two documents about the same event do not line up. Every difference cites both
documents by their public identifiers, so any reader can retrieve both and check it.

> **The one non-negotiable rule this tool is built around:** it reports differences between
> documents. It never states or implies that anything was concealed, left out improperly,
> under-reported, or done with intent, and it produces **no score and no match rate for any
> company**. A difference between two independently-maintained public records is normal, and
> usually has an ordinary explanation: different reporting thresholds, different timing, an
> error in either source, duplicate records, or the plain fact that the two sources were built
> for different purposes. Those explanations are attached to every finding.

---

## Why this exists

Auditing distinguishes two directions. **Vouching** starts from the records and works backward,
which catches overstatement. **Tracing** starts from an independent population and works
forward *into* the records, which is the only direction that can catch something missing from a
record that is otherwise complete, well-formed and verifiable.

A report that is filed, correctly formatted and internally consistent can still not line up
with what independent sources describe. No amount of checking the report against itself will
show that. It requires starting from a population the reporting party does not control.

`filing-check` runs in the tracing direction only, and never the reverse. A filing with no
corresponding complaint is not a finding and is not computed: consumer complaints exist for a
small, non-random slice of vehicles, so "no complaint corresponds to this filing" is the normal
state of almost every filing and means nothing.

---

## Methodology

### 1. The framing guard, and why it was built first

Both guards were written and proven green **before any matching or comparison logic existed**.
Of the 132 tests in this repo, the first 74 predate the first line of reconciliation code. A
tool that names real companies against real government records cannot have its reputation
safety added afterwards.

**Layer 1: the output guard (`framing_guard.py`).** Any tool-generated prose is scanned before
it can reach a reader, against two match layers:

- **Attribution constructions**: concealment attributed to a filer, duty-breach claims
  ("failed to report", "failed to disclose"), under-reporting, "evidence of concealment",
  "proves this was deliberate", regulatory-violation assertions, character judgments, intent
  attribution, company-level scores, and calls for enforcement.
- **Hard-banned lemmas**: words with no benign role in generated prose about a document
  comparison, banned even when negated. Stating the careful negated framing is the curated
  caveats' job, not generated text's.

Text that trips the guard is **discarded, not repaired**: a narrative that has drifted into
attributing intent cannot be patched into safety, and the deterministic report already carries
the whole finding.

One deliberate subtlety: `omit` is banned in generated prose even though it reads factual.
"The filing omitted X" presupposes that X belonged in it, which is a duty claim this tool has
no basis to make. The sanctioned phrasing carries the same information without it: **"X is not
present in the filing."**

Two boundaries the guard does *not* cross, both tested:
- **The curated caveats are not scanned.** Two of them name concealment and wrongdoing in order
  to disavow them, so they would trip the lemma layer by design. They are human-reviewed and
  verified by exact-content tests instead. A test pins the exemption at exactly those two, so
  it stays narrow.
- **Source text is not scanned.** A consumer complaint is an unverified self-report that may
  itself allege a cover-up. That text is the complainant's, republished verbatim and attributed.
  It must reach the reader, and it must never be restated as this tool's words.

The guard runs clean across roughly 90,000 lines of real rendered output.

**Layer 2: the data model cannot represent a verdict.** No model has a field for concealment,
intent, negligence, wrongdoing, or fault; a finding holds two cited records and the fields on
which they differ, and a test pins its exact field set. The finding vocabulary is deliberately
small and contains no kind that names concealment, omission, or a failure to report. The two
kinds are `UNMATCHED_INDEPENDENT_RECORD` and `FIELD_DIFFERENCE`.

### 2. Record linkage

Two records are linked only when **all three** conditions hold. No similarity score overrides
any of them:

1. **Same reporting entity**: resolved through a normalizing fuzzy matcher with a curated
   alias table for names that share no tokens.
2. **A shared 11-character VIN prefix**: the same vehicle configuration, model year and plant.
3. **Incident months within one month** of each other.

The gate is strict on purpose, because the costs are not symmetric. A wrong link *invents* a
difference between two unrelated events and attaches it to a named company. A missed link only
lowers a match rate that is disclosed. So the resolver is biased toward not linking.

**No linkage is treated as high confidence.** Neither source publishes VIN characters 12-17
(the serial that identifies an individual vehicle), so a shared prefix means a shared
configuration, which thousands of vehicles have. It is *required* for a linkage, because
without it "same manufacturer, same month" would link any of 1,536 Tesla filings to any Tesla
complaint in that month. It is *not sufficient* for confidence. Every match is labelled a
candidate for human verification.

The entity-resolution engine is a direct reuse of an approach applied four times before in this
portfolio: a three-band normalize-and-score matcher (auto-merge / adjudicate / distinct) with
a hard gate that similarity cannot override. What is specific here is that the unit is an
*incident* rather than an entity, and the gate is entity + configuration + month.

### 3. What is compared, and what deliberately is not

Two fields: **injury** and **fatality**. That is the honest extent of the overlap between the
two schemas. Consumer complaints carry no location; every filing in this population is a crash
report by construction, so "was it a crash" is trivially true; and tow, airbag, roadway,
weather and speed are filing-only fields with no counterpart. Comparing a field one source
never collects would manufacture findings out of schema mismatch.

**A comparison is skipped entirely whenever either side is indeterminate.** "Unknown" is the
injury severity on 1,576 of 1,800 Level 2 filings in this snapshot; treating it as "no injury"
would generate false differences at scale, against named companies. An indeterminate field is
not a disagreement.

### 4. Amended filings are kept separate

Filers sometimes amend their own filings, and the published data retains the superseded
versions. This tool reports which fields changed between versions, but in **its own section,
as its own type, excluded from the match rate**, because it compares a filing against a later
version of *itself* rather than against an independent source. The separation is structural: an
amendment is a different type from a finding and has no finding kind, so it cannot enter the
cross-source results even by mistake.

It also **never diffs narrative prose word by word**. Only *which* fields changed is reported.
A word-level diff of an incident narrative invites exactly the inference this tool refuses to
make: that what was added should have been there the first time. A filer amending its own
filing is the reporting system working as intended: new information arrives, the record is
corrected.

### 5. The match-rate disclosure pattern

The rate is a coverage statistic about *this tool's method*. Reported carelessly it would read
as a scoreboard about corporate honesty, so the disclosure is enforced in code rather than left
to editorial discipline:

- **The rate and its meaning are one object.** The match-rate object raises on construction if
  its interpretation text is empty, so **no code path can emit a bare percentage**: not the
  text report, not the JSON export, not any future consumer.
- **The rate appears before the findings.** A reader who meets a list of differences first has
  already formed an impression that a statistic at the end has to argue against.
- **The low result is pre-declared, not explained away afterwards.** The interpretation text
  states that a low rate is expected, and why.
- **A calibration benchmark travels with it** (below).
- **An empty population yields no rate at all**: never 0% or 100%. A rate over nothing is not
  a result, and rendering one would invent it.
- **There is no per-company breakdown, and none is representable.** The match-rate object has
  no field that could name a company, and the module that computes it takes no entity
  parameter. Both are tested.

**Why the per-company rate is refused.** It would read as "this company is missing N% of its
incidents." It cannot support that: it is dominated by whether a fleet is consumer-owned, by
fleet size, and by operating geography. Refusing it is the point, not a limitation.

---

## The headline result is a low match rate, and that is the expected outcome

First real run, snapshot 2026-08-09:

| | ADS filings | ADAS (Level 2) filings |
|---|---|---|
| Independent records examined | 1,181 | 1,181 |
| Linked to a filing | 0 | 44 |
| **Non-match rate** | **100%** | **96.3%** |

**This is not a finding about anyone's reporting.** The two populations barely overlap by
construction: consumer complaints are filed by vehicle owners, and a driverless fleet has no
owner to file one. The largest fleet in this snapshot accounts for 947 filings on a single
vehicle configuration, for which 18 consumer complaints exist in total, none of them a crash.

For calibration: EMIR's dual-sided trade reconciliation (mandatory, in a far more structured
domain, with both sides legally required to report the same transaction) still left up to
**55%** of trades unreconciled after four years. Cross-source reconciliation is genuinely messy
everywhere it has been attempted.

The substantive methodological result is narrower and more useful than a pass/fail: **with the
populations that are actually public and reachable without an account, cross-source
corroboration of automated-vehicle incident filings is close to unavailable in the driverless
case**, which is precisely where autonomy, and therefore interest in independent
corroboration, is highest.

**Essay:** [You cannot prove nothing was
hidden](docs/you-cannot-prove-nothing-was-hidden.md) sets this result in its wider context:
why tamper-evidence is a solved problem that does not reach a filed, well-formed report that
is wrong by omission, what the Cruise and Honda precedents show about how such omissions are
actually caught, and why the IAEA is the right benchmark for any claim that nothing was
hidden.

---

## Example of the methodology's output

> ### ⚠ Read this before the example below
>
> **This is a demonstration of what the tool emits, not a finding about a company.** It is
> included so the output format and its caveats can be inspected, and for no other purpose.
>
> - The linkage is **LOW confidence**, as *every* linkage this tool produces currently is.
> - The two records share a manufacturer, a **vehicle configuration** and a month. They do
>   **not** share an identified vehicle: the VIN serial is not published by either source.
>   **The two records may well describe entirely different events.**
> - A difference between a filing and a consumer complaint has many ordinary explanations:
>   different reporting thresholds, different timing, an error in either source, duplicate
>   records, or a wrong linkage. Consumer complaints are **unverified self-reports**.
> - **Pending further validation.** This is a single demonstration case from a first run. It
>   has not been independently checked, and it is **not a headline finding and should not be
>   treated as conclusive** or as evidence of anything about the named company's reporting.
> - Nothing here states or implies that anything was concealed, left out improperly, or done
>   with intent. The tool is structurally incapable of making that claim, and neither is this
>   README.

With that established, a single `FIELD_DIFFERENCE` was produced by the Level 2 run:

```
CHECKABLE DIFFERENCE -- a matched pair of records differs

  Independent record: NHTSA consumer complaint ODI 11693937
    Filed by:      a member of the public (unverified self-report)
    Manufacturer:  Tesla, Inc.
    Incident date: 10/14/2025   Complaint filed: 10/16/2025
    VIN prefix:    5YJ3E1EA5LF
    Source:        https://www.nhtsa.gov/?nhtsaId=11693937

  Filing: SGO report 13781-12029 version 2 (ADAS)
    Reporting entity: Tesla, Inc.
    Incident date:    OCT-2025   Location: Hesperia, CA
    Vehicle:          TESLA Model 3 2020   VIN prefix: 5YJ3E1EA5LF

  Record linkage: VIN_PREFIX_MONTH   [confidence: LOW]
    This linkage is a candidate, not an established fact that the two
    records describe the same event.

  Fields that differ:
    Injury reported:
      filing      [Highest Injury Severity Alleged]: Property Damage. No Injured Reported
      independent [numberOfInjuries]: 1 injuries reported
```

In the tool's actual output, this block is followed by all six innocent explanations and its
mandatory caveat, before a reader reaches any interpretation. Both documents are cited so the
comparison can be checked directly against the public sources rather than taken on trust.

**What would raise confidence in a case like this**, and none of it has been done here:
retrieving both source documents in full, checking whether the complaint describes a vehicle in
the same location, establishing whether the two records concern the same vehicle at all, and an
independent review of the linkage method itself.

---

## Findings about the public data itself

Three properties of the live sources were established during the build and materially shaped
the design. They are reported because they are useful to anyone else working with this data:

1. **California DMV's public listing of autonomous-vehicle collision reports (OL 316) is no
   longer reachable**, and the collision-reports link on the DMV's autonomous vehicles page now
   points to a dashboard built from NHTSA SGO data, the same population being checked, so it
   cannot serve as an independent source.
2. **Filings publish incident dates to month precision only** (e.g. `APR-2026`). The day is not
   published, so any comparison against them can only happen at month precision.
3. **The 11-character VIN prefix both sources publish identifies a vehicle configuration, not a
   vehicle.** Characters 12-17, the serial, are not published by either source.

---

## Known coverage gaps

Stated up front rather than discovered by a user:

- **Police-reported crash data (Berkeley TIMS / California SWITRS) is not included.** It is the
  population academic crash-rate research uses and would be the strongest independent source
  available, but it requires an account.
- **California DMV OL 316 collision reports are not included**, for the reason in the section
  above.
- **Court filings and news coverage are deferred**, not ruled out.
- **NHTSA consumer complaints are the only independent population in this version.** That
  single-source scope is the most important limit on everything reported here.

---

## Usage

```bash
python cli.py fetch                      # pin a dated snapshot of the public data
python cli.py reconcile --report-type ADAS
python cli.py reconcile --report-type ADS --entity Waymo --limit 5
python cli.py reconcile --json           # rate, findings, caveats, all sources
python cli.py amendments                 # filings amended by their own filer
python cli.py sources                    # sources, roles, and coverage gaps
python cli.py scope                      # scope and the standing disclaimer
```

Findings are computed against a pinned, dated snapshot, because NHTSA republishes the filing
CSVs on a rolling window: an unpinned run could not be reproduced by a reader later.

Requires Python 3.10+, `click` and `rich`. Run the tests with `python -m pytest tests/ -q`.

## Sources

- NHTSA Standing General Order 2021-01 incident reports: <https://www.nhtsa.gov/laws-regulations/standing-general-order-crash-reporting>
- NHTSA consumer complaints (ODI): <https://www.nhtsa.gov/report-a-safety-problem>

Full architecture, the data findings that shaped it, and the tensions between the framing
constraint and usefulness are in [`DESIGN.md`](DESIGN.md).
