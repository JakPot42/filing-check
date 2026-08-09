"""sgo.py -- load NHTSA Standing General Order 2021-01 incident filings.

The filings are the document under examination. They are loaded from a pinned, dated snapshot
so every finding is reproducible: NHTSA republishes these CSVs on a rolling window, so an
unpinned run could not be checked by a reader later.

Values are republished as written by the filer. Nothing here normalizes, corrects, or
interprets a filed value -- if a filing says "No Injured Reported", that string is what the
report shows, next to whatever the independent record says.
"""
from __future__ import annotations

import csv
import os

import config
from models import FilingRecord, Population, SourceRef

# NHTSA's own column names, kept literal so a reader can find each value in the published CSV.
_COL = {
    "report_id": "Report ID",
    "report_version": "Report Version",
    "reporting_entity": "Reporting Entity",
    "submission_date": "Report Submission Date",
    "incident_date": "Incident Date",
    "incident_time": "Incident Time (24:00)",
    "city": "City",
    "state": "State",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "vin_prefix": "VIN",
    "make": "Make",
    "model": "Model",
    "model_year": "Model Year",
    "highest_injury_severity": "Highest Injury Severity Alleged",
    "airbags_deployed": "Any Air Bags Deployed?",
    "vehicle_towed": "Was Any Vehicle Towed?",
    "investigating_agency": "Investigating Agency",
    "narrative": "Narrative",
    "narrative_cbi": "Narrative - CBI?",
}

# The filing's own statements about what data exists. Descriptive context only -- never a
# finding. That a filing indicates video is available says nothing about the filing's contents,
# and this tool does not treat it as if it did.
_DATA_AVAILABILITY_COLS = {
    "Data Availability - EDR": "EDR",
    "Data Availability - Police Rpt": "Police report",
    "Data Availability - Telematics": "Telematics",
    "Data Availability - Complaints": "Complaints",
    "Data Availability - Video": "Video",
    "Data Availability - Other": "Other",
    "Data Availability - No Data": "No data",
    "Data Availability - Unknown": "Unknown",
}

_SOURCE_COLS = {
    "Source - Complaint/Claim": "Complaint/claim",
    "Source - Telematics": "Telematics",
    "Source - Law Enforcement": "Law enforcement",
    "Source - Field Report": "Field report",
    "Source - Testing": "Testing",
    "Source - Media": "Media",
    "Source - Internal Process Review": "Internal process review",
    "Source - NHTSA VOQ": "NHTSA VOQ",
    "Source - State or Other Agency": "State or other agency",
    "Source - Other Entity": "Other entity",
}


def _is_yes(value: str) -> bool:
    return (value or "").strip().upper() in ("Y", "YES", "TRUE", "1")


def _flags(row: dict, columns: dict) -> list:
    return [label for col, label in columns.items() if _is_yes(row.get(col, ""))]


def snapshot_path(report_type: str) -> str:
    return os.path.join(config.SNAPSHOT_DIR, f"SGO-2021-01_Incident_Reports_{report_type}.csv")


def source_ref(report_type: str, retrieved_date: str) -> SourceRef:
    url = config.SGO_ADS_URL if report_type == "ADS" else config.SGO_ADAS_URL
    return SourceRef(
        source_id=Population.FILINGS,
        name=f"{config.SOURCES['NHTSA_SGO']['name']} ({report_type})",
        url=url,
        retrieved_date=retrieved_date,
        snapshot_label=f"SGO-2021-01 {report_type} CSV, retrieved {retrieved_date}",
    )


def load_filings(report_type: str = "ADS", retrieved_date: str = "",
                 path: str | None = None) -> list:
    """Load every filing row from the pinned snapshot, including superseded versions.

    Superseded versions are deliberately kept: they are what makes the amendment comparison
    possible. Callers that want only the current version of each report should use
    `latest_versions()`.
    """
    path = path or snapshot_path(report_type)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No pinned snapshot at {path}. Run `filingcheck fetch` to download the public "
            f"NHTSA CSV, or pass --path to point at your own copy."
        )
    ref = source_ref(report_type, retrieved_date)
    filings = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if not (row.get(_COL["report_id"]) or "").strip():
                continue
            filings.append(FilingRecord(
                report_id=row[_COL["report_id"]].strip(),
                report_version=(row.get(_COL["report_version"]) or "").strip(),
                reporting_entity=(row.get(_COL["reporting_entity"]) or "").strip(),
                report_type=report_type,
                submission_date=(row.get(_COL["submission_date"]) or "").strip(),
                incident_date=(row.get(_COL["incident_date"]) or "").strip(),
                incident_time=(row.get(_COL["incident_time"]) or "").strip(),
                city=(row.get(_COL["city"]) or "").strip(),
                state=(row.get(_COL["state"]) or "").strip(),
                latitude=(row.get(_COL["latitude"]) or "").strip(),
                longitude=(row.get(_COL["longitude"]) or "").strip(),
                vin_prefix=(row.get(_COL["vin_prefix"]) or "").strip(),
                make=(row.get(_COL["make"]) or "").strip(),
                model=(row.get(_COL["model"]) or "").strip(),
                model_year=(row.get(_COL["model_year"]) or "").strip(),
                highest_injury_severity=(row.get(_COL["highest_injury_severity"]) or "").strip(),
                airbags_deployed=(row.get(_COL["airbags_deployed"]) or "").strip(),
                vehicle_towed=(row.get(_COL["vehicle_towed"]) or "").strip(),
                investigating_agency=(row.get(_COL["investigating_agency"]) or "").strip(),
                narrative=(row.get(_COL["narrative"]) or "").strip(),
                narrative_cbi=(row.get(_COL["narrative_cbi"]) or "").strip(),
                declared_data_availability=_flags(row, _DATA_AVAILABILITY_COLS),
                declared_sources=_flags(row, _SOURCE_COLS),
                source=ref,
            ))
    return filings


def _version_key(filing: FilingRecord) -> int:
    try:
        return int(filing.report_version)
    except (TypeError, ValueError):
        return 0


def latest_versions(filings: list) -> list:
    """One filing per report id -- the highest version present in the snapshot."""
    latest: dict = {}
    for f in filings:
        current = latest.get(f.report_id)
        if current is None or _version_key(f) > _version_key(current):
            latest[f.report_id] = f
    return list(latest.values())


def version_groups(filings: list) -> dict:
    """report_id -> its versions, ascending. Only reports with more than one version are
    returned: those are the only ones an amendment comparison applies to."""
    groups: dict = {}
    for f in filings:
        groups.setdefault(f.report_id, []).append(f)
    return {rid: sorted(v, key=_version_key)
            for rid, v in groups.items() if len(v) > 1}
