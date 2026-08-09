"""config.py -- constants, source metadata, thresholds, scope. No logic.

Single source of truth for every tunable value and every cited public source.
"""
from __future__ import annotations

import os

TOOL_NAME = "filingcheck"
VERSION = "0.1.0"

# --- DEMO_MODE: permissive parse, portfolio-canonical -------------------------
def _demo_mode(env: dict | None = None) -> bool:
    env = os.environ if env is None else env
    return env.get("DEMO_MODE", "true").strip().lower() not in ("false", "0", "no", "off")


DEMO_MODE = _demo_mode()

# --- Scope --------------------------------------------------------------------
MVP_SCOPE = (
    "NHTSA Standing General Order (SGO 2021-01) incident filings reconciled against NHTSA "
    "consumer complaints"
)

# --- Sources (cited; pinned by snapshot) --------------------------------------
SGO_ADS_URL = "https://static.nhtsa.gov/odi/ffdd/sgo-2021-01/SGO-2021-01_Incident_Reports_ADS.csv"
SGO_ADAS_URL = "https://static.nhtsa.gov/odi/ffdd/sgo-2021-01/SGO-2021-01_Incident_Reports_ADAS.csv"
SGO_LANDING_URL = "https://www.nhtsa.gov/laws-regulations/standing-general-order-crash-reporting"
COMPLAINTS_API = "https://api.nhtsa.gov/complaints/complaintsByVehicle"
COMPLAINTS_LANDING_URL = "https://www.nhtsa.gov/report-a-safety-problem"

SOURCES = {
    "NHTSA_SGO": {
        "name": "NHTSA Standing General Order 2021-01 incident reports",
        "url": SGO_LANDING_URL,
        "role": "the filings under examination",
    },
    "NHTSA_COMPLAINTS": {
        "name": "NHTSA consumer complaints (ODI)",
        "url": COMPLAINTS_LANDING_URL,
        "role": "independent population -- filed by consumers, not by the reporting party",
    },
}

# --- Snapshot -----------------------------------------------------------------
# Findings are computed against a pinned, dated copy of the public data so any reader can
# reproduce them exactly. NHTSA republishes the SGO CSVs on a rolling window, so an unpinned
# run would not be reproducible.
SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots")

# --- Record-linkage thresholds ------------------------------------------------
# Lineage: GhostTrace entity_resolver -> tech-scanner -> PatientFusion -> entity-graph -> here.
# Three bands, unchanged: auto-merge / adjudicate / distinct.
FUZZY_AUTO_MERGE_THRESHOLD = 90    # entity name similarity for an automatic entity merge
FUZZY_ADJUDICATE_THRESHOLD = 80    # below auto-merge: a candidate, never merged unattended

# The HARD GATE on incident linkage. Every prior deployment of this resolver carried one --
# GhostTrace's jurisdiction gate, PatientFusion's DOB gate. Here it is entity + vehicle
# configuration + month. All three must hold; no similarity score overrides any of them. A
# wrong link manufactures a difference between two unrelated events and attaches it to a named
# company, which is the worst output this tool can emit.
#
# **Month, not day, because that is the precision the public data actually has.** SGO filings
# publish the incident date as a month only ("APR-2026"); NHTSA does not publish the day.
# Complaints carry a full date. So the finest gate the filing side can support is the month,
# and a day-level tolerance would be a precision this tool does not have.
INCIDENT_MONTH_TOLERANCE = 1

# **A shared VIN prefix is REQUIRED for a linkage, and still does not make one reliable.**
# Both populations publish an 11-character VIN prefix: WMI + VDS + check digit + model year +
# plant. The serial (characters 12-17) -- the part that identifies an individual vehicle -- is
# not published by either source. So a shared prefix means "same vehicle configuration, year
# and plant", which thousands of vehicles share. It is NOT a shared vehicle.
#
# It is required because without it there is no basis at all: manufacturer plus month would
# link any of 1,536 Tesla filings to any Tesla complaint in the same month, which is not
# evidence that two records describe the same event.
REQUIRE_VIN_PREFIX_FOR_LINKAGE = True

# Consequently NO linkage method qualifies as high confidence in this version. Every match is
# a candidate for human verification -- the candidates-only posture inherited from GhostTrace's
# ofac_checker through tie-check. The constant stays so that a genuinely identifying key, if
# either source ever publishes one, can be added here deliberately rather than by drift.
HIGH_CONFIDENCE_METHODS = ()

# --- Anthropic (optional narrative only; never decides a finding) -------------
CLAUDE_MODEL = "claude-haiku-4-5-20251001"   # pinned, GO-2 discipline

# --- Fields compared on a matched pair ----------------------------------------
# Deliberately short, and shorter than it first looks like it should be. Each entry is a field
# BOTH populations genuinely carry. Fields only one source collects are NOT compared:
# "absent from a source that never collects it" is not a difference, and presenting it as one
# would manufacture findings out of schema mismatch.
#
# What this rules out, checked against the real data rather than assumed:
#   - location: consumer complaints carry no city or state at all.
#   - crash indication: every SGO filing is a crash report by construction, so the comparison
#     is trivially true and tells a reader nothing.
#   - tow, airbag, roadway, weather, speed: filing-only fields with no complaint counterpart.
# What remains is injury and fatality. Two fields is the honest extent of the overlap.
COMPARED_FIELDS = ("injury", "fatality")

# Filing injury-severity values that positively state NO injury. Anything outside this set and
# outside INJURY_INDETERMINATE below is treated as an injury having been reported.
FILING_NO_INJURY_VALUES = (
    "No Injured Reported",
    "Property Damage. No Injured Reported",
)

# Values that state nothing either way. A comparison against these NEVER produces a
# difference -- an indeterminate field is not a disagreement. This matters more than it looks:
# "Unknown" is the injury severity on 1,576 of 1,800 Level 2 filings in the August 2026
# snapshot, so treating it as "no injury" would generate false differences at scale.
INJURY_INDETERMINATE = ("Unknown", "")

FILING_FATALITY_VALUE = "Fatality"
