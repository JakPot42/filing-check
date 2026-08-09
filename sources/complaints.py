"""complaints.py -- load NHTSA consumer complaints: the independent population.

Independent in the sense that matters here: these records are filed by members of the public,
not by the party whose filings are being checked. NHTSA publishes them as received and states
they are unverified.

Two real obstacles this module handles, both discovered by querying the live API rather than
assumed:

  1. **The complaints database uses its own model vocabulary.** The SGO CSV says
     `Model Y`; the complaints API only answers to `MODEL Y (All Variants)`, and returns a
     silent zero-result for anything else. The valid vocabulary comes from NHTSA's own
     /products/vehicle/models endpoint and is matched with the portfolio's fuzzy resolver.
     A silent zero is the dangerous failure mode here: it looks exactly like "no independent
     records exist", which would understate the independent population and make the filings
     look better corroborated than they are. `ConfigResolution.resolved` records whether a
     configuration was actually queryable so the report can say so.

  2. **Only crash-flagged complaints are eligible.** The SGO population is a crash-report
     population. A complaint about a rattle has no possible counterpart in it, and counting
     those as unmatched would inflate the non-match rate with records that were never
     reconcilable in the first place.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass

import config
from models import IndependentRecord, Population, SourceRef
from resolve.incident_resolver import similarity

_MODELS_ENDPOINT = "https://api.nhtsa.gov/products/vehicle/models"
_TIMEOUT = 30


@dataclass
class ConfigResolution:
    """One SGO vehicle configuration, and whether it could be queried at all."""
    make: str
    model: str
    model_year: str
    resolved_model: str | None = None
    match_score: int = 0
    resolved: bool = False
    note: str = ""


def source_ref(retrieved_date: str) -> SourceRef:
    return SourceRef(
        source_id=Population.NHTSA_COMPLAINTS,
        name=config.SOURCES["NHTSA_COMPLAINTS"]["name"],
        url=config.SOURCES["NHTSA_COMPLAINTS"]["url"],
        retrieved_date=retrieved_date,
        snapshot_label=f"NHTSA complaints API, retrieved {retrieved_date}",
    )


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "filingcheck/0.1 (public-data)"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def available_models(make: str, model_year: str) -> list:
    """NHTSA's own model vocabulary for a make/year, from its published endpoint."""
    query = urllib.parse.urlencode({"modelYear": model_year, "make": make, "issueType": "c"})
    try:
        data = _get_json(f"{_MODELS_ENDPOINT}?{query}")
    except Exception:
        return []
    return sorted({(r.get("model") or "").strip()
                   for r in data.get("results", []) if (r.get("model") or "").strip()})


def resolve_config(make: str, model: str, model_year: str) -> ConfigResolution:
    """Map an SGO (make, model, year) onto the complaints database's vocabulary.

    Fifth-deployment reuse of the portfolio's fuzzy resolver, applied to vehicle model names.
    An exact normalized match wins; otherwise the best fuzzy candidate above the adjudicate
    threshold is used and recorded with its score, so the report can show how the independent
    population was located."""
    resolution = ConfigResolution(make=make, model=model, model_year=model_year)
    candidates = available_models(make, model_year)
    if not candidates:
        resolution.note = (
            f"NHTSA lists no complaint-eligible models for {make} {model_year}; no independent "
            f"records could be requested for this configuration."
        )
        return resolution

    best, best_score = None, 0.0
    for candidate in candidates:
        score = similarity(model, candidate)
        if score > best_score:
            best, best_score = candidate, score

    if best is not None and best_score >= config.FUZZY_ADJUDICATE_THRESHOLD:
        resolution.resolved_model = best
        resolution.match_score = int(round(best_score))
        resolution.resolved = True
        resolution.note = (
            f"SGO model name {model!r} matched to complaints-database model {best!r} "
            f"({int(round(best_score))}/100)."
        )
    else:
        resolution.match_score = int(round(best_score))
        resolution.note = (
            f"SGO model name {model!r} could not be matched to any model name the complaints "
            f"database recognises for {make} {model_year} (best candidate "
            f"{best!r} at {int(round(best_score))}/100). No independent records were "
            f"requested for this configuration."
        )
    return resolution


def _to_record(raw: dict, ref: SourceRef) -> IndependentRecord:
    return IndependentRecord(
        population_id=Population.NHTSA_COMPLAINTS,
        record_ref=str(raw.get("odiNumber", "")).strip(),
        entity_name=(raw.get("manufacturer") or "").strip(),
        incident_date=(raw.get("dateOfIncident") or "").strip(),
        filed_date=(raw.get("dateComplaintFiled") or "").strip(),
        vin_prefix=(raw.get("vin") or "").strip(),
        is_crash=bool(raw.get("crash")),
        injuries_reported=raw.get("numberOfInjuries"),
        deaths_reported=raw.get("numberOfDeaths"),
        components=(raw.get("components") or "").strip(),
        # The complainant's own words, republished verbatim and attributed. Never restated as
        # this tool's words, and never routed through framing_guard (see that module).
        summary_quoted=(raw.get("summary") or "").strip(),
        source_url=f"https://www.nhtsa.gov/?nhtsaId={raw.get('odiNumber', '')}",
        source=ref,
    )


def fetch_for_config(resolution: ConfigResolution, ref: SourceRef,
                     crash_only: bool = True) -> list:
    """Fetch the independent records for one resolved configuration."""
    if not resolution.resolved or not resolution.resolved_model:
        return []
    query = urllib.parse.urlencode({
        "make": resolution.make,
        "model": resolution.resolved_model,
        "modelYear": resolution.model_year,
    })
    try:
        data = _get_json(f"{config.COMPLAINTS_API}?{query}")
    except Exception:
        return []
    records = [_to_record(r, ref) for r in data.get("results", [])
               if not crash_only or r.get("crash")]
    return [r for r in records if r.record_ref]


def snapshot_path(label: str = "complaints") -> str:
    return os.path.join(config.SNAPSHOT_DIR, f"{label}.json")


def save_snapshot(records: list, resolutions: list, retrieved_date: str,
                  label: str = "complaints") -> str:
    os.makedirs(config.SNAPSHOT_DIR, exist_ok=True)
    path = snapshot_path(label)
    payload = {
        "retrieved_date": retrieved_date,
        "source": config.SOURCES["NHTSA_COMPLAINTS"],
        "crash_only": True,
        "configurations": [vars(r) for r in resolutions],
        "records": [
            {k: v for k, v in vars(rec).items() if k != "source"} for rec in records
        ],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1)
    return path


def load_snapshot(label: str = "complaints") -> tuple:
    """Return (records, resolutions, retrieved_date) from the pinned snapshot."""
    path = snapshot_path(label)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No pinned complaints snapshot at {path}. Run `filingcheck fetch` first."
        )
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    retrieved_date = payload.get("retrieved_date", "")
    ref = source_ref(retrieved_date)
    records = [IndependentRecord(source=ref, **raw) for raw in payload.get("records", [])]
    resolutions = [ConfigResolution(**raw) for raw in payload.get("configurations", [])]
    return records, resolutions, retrieved_date
