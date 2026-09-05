# You cannot prove nothing was hidden

I built two tools this year that sit on opposite sides of one problem.

The first is a tamper-evident log: every entry hashed, committed to a Merkle tree, any
retroactive edit detectable against an archived root. It works. The second checks public
autonomous-vehicle incident filings against independent public records the filer does not
control. That one produced a result I did not expect and could not argue away, and it is the
reason I am writing this.

The short version: tamper-evidence is finished work, the thing people actually want is not
tamper-evidence, and the thing they actually want cannot be delivered by any mechanism I know
of, including every mechanism I have built or read about.

This matters now because a lot of people are building logging for autonomous systems.
Vehicles, agents, robots, anything that acts without a person watching each action. The pitch
is nearly always some version of full visibility, complete audit trail, provable record of
what the system did. I want to be precise about which part of that is real and why the gap is
not a backlog item.

## The part that works

Tamper-evidence has been solved for a while.

Put every record into a Merkle tree. Each leaf is the hash of one entry, each internal node is
the hash of its two children, and the root is a single commitment over the whole ordered
sequence. Change one byte in entry 4,112 and every ancestor hash changes up to the root, so
publishing the root makes the alteration visible to anyone holding the old one. Inclusion
proofs are logarithmic, so you can prove one record was present without handing over the log.

That is the tool I mentioned first. The five tests that matter write a real journal to disk,
corrupt it, and assert the specific failure, because a tamper-evidence claim tested only on
the happy path is not evidence of anything.

Above that layer the ecosystem has better machinery than I could build. Certificate
Transparency is the flagship. Consistency proofs make append-only enforcement structural: if
the operator reorders or deletes any historical entry, no valid consistency proof between the
old root and the new one can exist. The math does not permit a cover-up. It permits only a
refusal to produce a proof, which is itself the signal. Witness cosigning, specified as C2SP
tlog-witness, closes the remaining hole where an operator shows two internally consistent
versions of the log to two different audiences. A witness that has cosigned checkpoint A
cannot later cosign a checkpoint B that is not a consistent extension of A, and it does this
while storing exactly one checkpoint per log, at under a second of added latency. Below all of
that, RFC 3161 timestamping has been available off the shelf for decades.

So: none of this is the hard part. All of it works, and the argument that follows is not
cryptographic pessimism. The cryptography is fine. It answers a different question than the
one people think they are asking.

Certificate Transparency says as much about itself, in RFC 9162 section 11.3: the log auditing
mechanisms can be circumvented by a misbehaving log that shows inconsistent views of itself to
different clients, so it is necessary to treat each log as a trusted third party. That is the
most successful deployed system of this kind conceding in its own specification that the math
alone does not remove trust in the operator. What removes it is the surrounding population of
independent monitors, and that population is the part you cannot build yourself.

## The failure that is out of reach

Here is the record I care about. It is well-formed. It is signed by the device, committed to a
Merkle tree, cosigned by independent witnesses, published somewhere the operator cannot
retract, and it verifies. Every layer above reports it as good.

It is also false, because of what is not in it.

No anchoring mechanism reaches this, and not partially. The mechanism has no view of what was
never submitted; it commits to the bytes it was given. If those bytes are an accurate account
of an incident with one paragraph removed, the commitment is over the version with the
paragraph removed, and it is a perfect commitment.

It helps to separate three things that get discussed as one problem.

**Never created.** The device is silent and no record exists. Anchoring cannot touch this at
all.

**Created but never submitted.** The record exists on the device and is withheld. Anchoring
reaches this partly: if the device numbers its own records and the log commits to those
numbers, a gap becomes visible. That relocates the question to whether the device's counter
can be trusted, which is a hardware question rather than a ledger question.

**Submitted but materially incomplete.** A record is filed, and it is wrong by omission.
Anchoring does not reach this, and there is no partial credit available.

The third one is the one that has actually happened.

## What actually happened

On October 2, 2023, in San Francisco, a pedestrian was struck by a human-driven vehicle and
thrown into the path of a Cruise vehicle operating without a driver. The Cruise vehicle ran
over her and stopped. Its detection system did not register that a person was underneath it,
so it then attempted a pullover maneuver and dragged her more than twenty feet.

Cruise filed a report with NHTSA describing the crash. The report omitted the secondary
movement and the dragging. In a videoconference with transportation officials the next
morning, Cruise employees gave a summary that also left the dragging out.

In 2024 Cruise agreed to a NHTSA consent order carrying a $1.5 million civil penalty and a
corrective action plan, and separately admitted to providing a false record to NHTSA with
intent to impede a federal investigation, resolved through a three-year deferred prosecution
agreement and a $500,000 criminal fine.

Note which part is load-bearing. The initial impact was not the autonomous vehicle's doing.
The dragging was, and so was the omission of it, which the company has admitted in a federal
criminal resolution.

The detail that should stop you is how the omission was found. NHTSA requested the video
footage, watched it, and compared it against the reports. What caught it was an independent
artifact, obtained by a regulator with the authority to demand it and reviewed by a person.
Nothing about the record itself was involved.

Any anchoring layer I could have designed would have marked those reports verified, because
they were: filed on time, well-formed, internally consistent. The failure was inside the
record.

Honda paid $70 million in 2015 for underreporting deaths and injuries under the TREAD regime.
Same shape. A mandated reporting duty discharged incompletely, found from outside.

## Two fields that say the same thing in different vocabulary

Auditing has treated this as a first-class problem for a century, with better words for it
than software has.

The existence assertion asks whether the recorded things really happened. You test it by
vouching, which moves backward from a record out to its source. It catches overstatement.

The completeness assertion asks whether all the things that happened were recorded. You test
it by tracing, which moves forward from an independent source population into the records. It
catches omission.

The consequence is structural, and I think it is the single most useful sentence in this
area: you cannot test completeness by examining the records. Testing completeness requires
starting from a population outside the system being tested, one the operator does not control.
Everything else here is a restatement of that.

Distributed systems arrives at the same place by another road, using the same word. A failure
detector has completeness, meaning it suspects every process that has genuinely failed, and
accuracy, meaning it never suspects a correct one. In an asynchronous system you cannot have
both, because you cannot distinguish a crashed process from a slow one. That is the FLP
setting, and the Chandra-Toueg hierarchy exists to characterize the minimum extra assumption
needed to get around it.

Translated: a device that was silenced and a device that operated correctly and had nothing to
report are observationally identical. Not under-engineered. Identical.

## The bar nobody clears

If the question is whether absence can be verified at all given unlimited motivation, there is
a benchmark, and it is humbling.

The IAEA draws two explicitly different conclusions about a state. One is that declared nuclear
material remained in peaceful activities, which is correctness of what was declared. The other,
called the broader conclusion, is that all nuclear material remained in peaceful activities,
requiring no indication of anything undeclared anywhere in the state. That second one is
genuine completeness, and reaching it requires an Additional Protocol in force: expanded
declarations, complementary access, environmental sampling. A legal right of physical entry
and independent measurement.

The figures below are from the IAEA Safeguards Statement for 2024, published June 2025. They
move every year, so the year matters as much as the numbers. In 2024 the IAEA applied
safeguards for 190 states. Of those, 137 had both a comprehensive safeguards agreement and an
Additional Protocol in force, which is the precondition for the broader conclusion. The broader
conclusion was drawn for 75. For the rest, evaluations regarding the absence of undeclared
material remained ongoing. Drawing the initial broader conclusion for one state can take
several years.

So the most intrusive, best-resourced, treaty-backed absence-verification regime that exists,
with inspectors on site and soil samples in hand and decades of accumulated method, reaches an
absence conclusion for well under half its subjects, and takes years each. Any product
claiming to prove nothing was hidden is claiming something the IAEA cannot reliably deliver
with people on the ground. That is the comparison I make when I see the claim in a deck, and I
have not yet seen one survive it.

## What is actually available

The picture is narrower than the marketing, not hopeless. Every domain I looked at converged
on the same three moves, and none of them prove absence.

**Remove the human curation step.** This is the one that touches the third failure mode, and
it is a design constraint rather than a new mechanism, which is why it is affordable. On a
trigger, capture a defined, immutable window of machine-generated telemetry, the whole window,
not a summary, with the boundaries published in advance. The Cruise vehicle's own sensor data
recorded the pullover maneuver; the omission happened in a report about the incident. If
nobody selects what goes in, nobody can leave something out. The cost is real: full windows
are far more privacy-sensitive than summaries, which collides with the confidentiality that
makes the data collectable at all.

**Make silence a filing.** Require a positive affirmation on a committed cadence, and have an
independent party watching for its absence. This is the heartbeat in distributed systems and
the nil return in tax compliance, where the principle is that there is no such thing as
nothing to declare and a missed nil return is recorded as a default. Aviation's version is the
strongest: under GADSS, aircraft position is reported at least every fifteen minutes, and once
per minute in distress, with the absence detected by the receiver who expected the message.
This does not prove nothing happened. It converts an invisible non-event into an attributable
violation.

**Corroborate against a population you do not control.** The tracing direction, and the only
family that reaches the third mode at all. The financial precedent is EMIR, where both
counterparties to a trade report it separately and a repository pairs and matches them across
fifty-three fields. It works, and it is a mess: after four years, up to fifty-five percent of
trades could not be reconciled.

## What happened when I tested the third one

I did not want to leave that as a recommendation, so I built it. A tool that reconciles NHTSA
Standing General Order filings against independent public populations, using only sources that
need no account and no relationship with anyone.

The live data changed the design before it changed my mind about anything else. California
DMV's public listing of autonomous-vehicle collision reports returns a 404, and the replacement
route the DMV's own page now offers points at a dashboard built from the NHTSA data being
checked, which would make the reconciliation circular. The eleven-character VIN prefix both
populations publish identifies a configuration, not a vehicle, so no linkage the tool produces
is high confidence.

Then the result. Against 1,181 independent records: zero linked to a driverless filing,
forty-four linked to a Level 2 filing. Match rates of 0.0 and 3.7 percent, worse than EMIR's
fifty-five percent by a wide margin, for a reason visible in the data rather than in the
method. The largest driverless fleet in the filings is a single vehicle model with 947
filings, for which eighteen consumer complaints exist, and not one of them is a crash.

A driverless fleet has no owner to file a complaint.

That is the finding I did not expect. The independent population, the one thing that can catch
a filed-but-incomplete report, is structurally weakest exactly where autonomy is highest, which
is exactly where independent corroboration matters most. The one population that would work is
police-reported crash data, and it is behind an account.

Be careful about what that number is. A 96 to 100 percent non-match rate measures this
method's reach across two populations that were never built to agree. It is no evidence that
any filing is missing or incomplete, and the tool is built so that it structurally cannot say
otherwise. What it measures is how much corroboration exists. It says nothing about anyone's
conduct.

## What you can and cannot claim

Here is where I have landed.

You can prove a record was not altered after it was written. You can prove that neither the
operator nor the company running the ledger can rewrite history without producing two
contradictory signed statements, either of which is permanent evidence against them, and you
can prove that to someone who does not trust you. You can make a gap in a sequence visible.
You can make silence into a logged, attributable violation instead of nothing at all. You can
guarantee that a record is a complete fixed window rather than a summary, so that no party
chose what to include.

You cannot prove that the telemetry inside the window is accurate. You cannot prove the trigger
fired every time it should have, and if the operator controls the definition of a reportable
event then the omission simply moves upstream of the logger, where nothing downstream can see
it. And you cannot prove that nothing was hidden.

Claim the first list. Disclaim the second, in the documentation and in the sales conversation
and on the dashboard, in the same words each time. The alternative is a marketing resolution
to an engineering gap, and the gap does not care.

So notice which question your mechanism answers. Integrity and completeness sound adjacent and
are not. Every hour spent on better anchoring goes into a problem that is already solved, and
none of it moves the completeness needle by any amount. If you want to move that needle, the
work is not cryptographic at all. It is finding a population you do not control, and then
reporting how thin it turns out to be. Mine was nearly empty.

---

## Sources

- [NHTSA, Consent Order: Cruise, Standing General Order reporting (2024)](https://www.nhtsa.gov/document/consent-order-cruise-standing-general-order-reporting)
- [U.S. Attorney's Office, N.D. Cal., Cruise admits to submitting a false report to influence a federal investigation](https://www.justice.gov/usao-ndca/pr/cruise-admits-submitting-false-report-influence-federal-investigation-and-agrees-pay)
- [NPR, Honda fined $70 million for underreporting deaths and injuries (2015)](https://www.npr.org/blogs/thetwo-way/2015/01/08/375914334/honda-fined-70-million-for-underreporting-deaths-and-injuries)
- [NHTSA, Standing General Order on Crash Reporting](https://www.nhtsa.gov/laws-regulations/standing-general-order-crash-reporting)
- [IAEA, Safeguards Statement for 2024 (published June 2025)](https://www.iaea.org/newscenter/news/iaea-applied-safeguards-for-190-states-iaea-report)
- [IAEA, Drawing safeguards conclusions](https://www.iaea.org/topics/drawing-safeguards-conclusions)
- [RFC 9162, Certificate Transparency Version 2.0](https://www.rfc-editor.org/rfc/rfc9162.html)
- [C2SP, tlog-witness specification](https://github.com/C2SP/C2SP/blob/main/tlog-witness.md)
- [Filippo Valsorda, Building a Transparent Keyserver](https://words.filippo.io/keyserver-tlog/)
- [ACCA, The audit of assertions](https://www.accaglobal.com/us/en/student/exam-support-resources/fundamentals-exams-study-resources/f8/technical-articles/assertions.html)
- [The Paper Trail, A Brief Tour of FLP Impossibility](https://www.the-paper-trail.org/post/2008-08-13-a-brief-tour-of-flp-impossibility/)
- [ICAO, Understanding GADSS](https://www.icao.int/operational-safety/Understanding-GADSS)
- [Kaizen Reporting, EMIR trade reporting: pairing and matching](https://www.kaizenreporting.com/emir-pairing-and-matching/)
