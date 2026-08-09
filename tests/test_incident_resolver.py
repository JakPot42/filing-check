"""Tests for the record-linkage layer -- fifth deployment of the portfolio's resolver.

The gate is the subject of most of these. A wrong link manufactures a difference between two
unrelated events and attaches it to a named company; a missed link only lowers a match rate
that is disclosed. Those costs are not symmetric, so the gate is tested for what it REFUSES at
least as hard as for what it accepts.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from models import FilingRecord, IndependentRecord, Population
from resolve.incident_resolver import (
    best_link,
    build_index,
    canonical_entity,
    entity_similarity,
    link,
    month_delta,
    normalize_name,
    parse_month,
    passes_gate,
    similarity,
)


def _filing(entity="Tesla, Inc.", vin="5YJ3E1EA5LF", date="OCT-2025", report_id="R1",
            version="1", severity="Property Damage. No Injured Reported"):
    return FilingRecord(report_id=report_id, report_version=version, reporting_entity=entity,
                        report_type="ADAS", incident_date=date, vin_prefix=vin,
                        highest_injury_severity=severity)


def _record(entity="Tesla, Inc.", vin="5YJ3E1EA5LF", date="10/14/2025", ref="1001",
            injuries=0, deaths=0):
    return IndependentRecord(population_id=Population.NHTSA_COMPLAINTS, record_ref=ref,
                             entity_name=entity, incident_date=date, vin_prefix=vin,
                             is_crash=True, injuries_reported=injuries, deaths_reported=deaths)


# --- date handling: the filings only have month precision ---------------------

def test_parse_month_handles_the_month_only_format_filings_actually_use():
    # NHTSA publishes the SGO incident date as a month. This is the real format, not a guess.
    assert parse_month("APR-2026") == (2026, 4)
    assert parse_month("OCT-2025") == (2025, 10)


def test_parse_month_also_handles_the_full_dates_complaints_carry():
    assert parse_month("10/14/2025") == (2025, 10)


def test_parse_month_returns_none_rather_than_guessing():
    assert parse_month("") is None
    assert parse_month("not a date") is None


def test_month_delta_crosses_year_boundaries():
    assert month_delta("DEC-2025", "01/05/2026") == 1
    assert month_delta("JAN-2026", "12/20/2025") == 1
    assert month_delta("OCT-2025", "10/14/2025") == 0


def test_month_delta_is_none_when_either_side_is_unparseable():
    assert month_delta("OCT-2025", "") is None
    assert month_delta("", "10/14/2025") is None


# --- the gate -----------------------------------------------------------------

def test_gate_admits_same_entity_same_vin_same_month():
    passes, note = passes_gate(_filing(), _record())
    assert passes
    assert "shared VIN prefix" in note


def test_gate_refuses_a_different_reporting_entity():
    passes, note = passes_gate(_filing(entity="Tesla, Inc."),
                               _record(entity="Ford Motor Company"))
    assert not passes
    assert "different reporting entity" in note


def test_gate_refuses_a_different_vehicle_configuration():
    passes, note = passes_gate(_filing(vin="5YJ3E1EA5LF"), _record(vin="7SAYGDEE8PF"))
    assert not passes
    assert "different vehicle configuration" in note


def test_gate_refuses_when_a_vin_prefix_is_absent():
    """Manufacturer plus month is not evidence that two records describe the same event: it
    would link any of 1,536 Tesla filings to any Tesla complaint in the same month."""
    passes, note = passes_gate(_filing(vin=""), _record())
    assert not passes
    assert "no VIN prefix" in note
    passes, _ = passes_gate(_filing(), _record(vin=""))
    assert not passes


def test_gate_refuses_beyond_the_month_tolerance():
    passes, note = passes_gate(_filing(date="JAN-2025"), _record(date="10/14/2025"))
    assert not passes
    assert "beyond the" in note


def test_gate_refuses_an_unparseable_date_rather_than_treating_it_as_satisfied():
    passes, note = passes_gate(_filing(date=""), _record())
    assert not passes
    assert "unparseable" in note


def test_gate_is_not_overridden_by_a_perfect_entity_score():
    """The entity name matches perfectly and everything else is identical, but the VIN prefix
    differs -- no similarity score may override the gate."""
    assert entity_similarity("Tesla, Inc.", "Tesla, Inc.") == 100.0
    assert link(_filing(vin="AAAAAAAAAAA"), _record(vin="BBBBBBBBBBB")) is None


# --- what a match claims, and does not -----------------------------------------

def test_no_linkage_is_high_confidence_in_this_version():
    """A shared 11-character VIN prefix is a vehicle configuration, year and plant -- not an
    individual vehicle, since neither source publishes characters 12-17. Nothing here may
    claim otherwise."""
    assert config.HIGH_CONFIDENCE_METHODS == ()
    match = link(_filing(), _record())
    assert match is not None
    assert match.match_confidence == "LOW"
    assert "not an individual vehicle" in match.gate_note


def test_match_records_the_month_difference_not_a_day_difference():
    match = link(_filing(date="OCT-2025"), _record(date="11/02/2025"))
    assert match is not None
    assert match.date_delta_months == 1


# --- entity resolution: reused lineage ----------------------------------------

def test_normalize_name_strips_corporate_suffixes():
    assert normalize_name("Tesla, Inc.") == "tesla"
    assert normalize_name("General Motors, LLC") == "general"
    assert normalize_name("Subaru of America, Inc.") == "subaru"


def test_known_alias_bridges_names_that_share_no_tokens():
    # The entity-graph lesson: fuzzy matching alone cannot bridge these.
    assert canonical_entity("Cruise") == "General Motors, LLC"
    assert similarity("Cruise", "General Motors, LLC") < config.FUZZY_AUTO_MERGE_THRESHOLD


def test_similarity_is_symmetric_and_bounded():
    assert similarity("Tesla, Inc.", "Tesla Inc") == 100.0
    assert 0.0 <= similarity("Ford Motor Company", "Tesla, Inc.") <= 100.0


# --- the index is a lookup path to the gate, not a second copy of it ----------

def test_index_and_scan_agree():
    filings = [_filing(report_id="A", vin="AAAAAAAAAAA"),
               _filing(report_id="B", vin="5YJ3E1EA5LF"),
               _filing(report_id="C", vin="5YJ3E1EA5LF", date="JAN-2020")]
    record = _record()
    via_index = best_link(record, build_index(filings))
    via_list = best_link(record, filings)
    assert via_index is not None and via_list is not None
    assert via_index.filing_report_id == via_list.filing_report_id == "B"


def test_index_drops_only_rows_the_gate_would_refuse_anyway():
    filings = [_filing(report_id="no-vin", vin=""), _filing(report_id="no-date", date="")]
    assert build_index(filings) == {}
    assert best_link(_record(), filings) is None


def test_best_link_returns_none_when_the_record_itself_cannot_clear_the_gate():
    filings = [_filing()]
    assert best_link(_record(vin=""), filings) is None
    assert best_link(_record(date=""), filings) is None


def test_best_link_prefers_the_closest_month():
    filings = [_filing(report_id="far", date="DEC-2025"),
               _filing(report_id="near", date="OCT-2025")]
    match = best_link(_record(date="10/14/2025"), filings)
    assert match is not None
    assert match.filing_report_id == "near"
    assert match.date_delta_months == 0
