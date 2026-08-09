"""cli.py -- filingcheck command-line interface.

Commands:
  fetch        download the public NHTSA data and pin it as a dated snapshot
  reconcile    reconcile a filing population against the independent population
  amendments   list filings amended by their own filer (not a cross-source check)
  sources      show the public sources, their roles, and the known coverage gaps
  scope        print the tool's scope and the standing framing disclaimer

Every command prints the standing SCOPE_DISCLAIMER. ASCII-safe output for Windows cp1252.
"""
from __future__ import annotations

import datetime
import json as _json

import click
from rich.console import Console

import config
import disclaimers
from pipeline import run
from report.render import render_text, to_json
from sources import complaints as complaints_src
from sources import sgo as sgo_src

console = Console()


def _today() -> str:
    return datetime.date.today().isoformat()


def _scope_banner() -> None:
    console.print(f"[dim]{disclaimers.SCOPE_DISCLAIMER}[/dim]")
    console.print(f"[dim]Scope: {config.MVP_SCOPE}. DEMO_MODE={config.DEMO_MODE}.[/dim]\n")


@click.group()
def cli() -> None:
    """filingcheck -- checkable differences between public incident filings and independent
    public records. Never a verdict about a company."""


@cli.command()
@click.option("--report-type", type=click.Choice(["ADS", "ADAS", "both"]), default="both",
              help="Which SGO filing population to download.")
def fetch(report_type: str) -> None:
    """Download the public NHTSA data and pin it as a dated snapshot.

    Findings are computed against the pinned copy so any reader can reproduce them: NHTSA
    republishes the SGO CSVs on a rolling window, so an unpinned run could not be checked
    later."""
    import os
    import urllib.request

    _scope_banner()
    today = _today()
    os.makedirs(config.SNAPSHOT_DIR, exist_ok=True)

    types = ["ADS", "ADAS"] if report_type == "both" else [report_type]
    configs: dict = {}
    for rt in types:
        url = config.SGO_ADS_URL if rt == "ADS" else config.SGO_ADAS_URL
        dest = sgo_src.snapshot_path(rt)
        console.print(f"Downloading {rt} filings ...", markup=False)
        urllib.request.urlretrieve(url, dest)
        filings = sgo_src.load_filings(rt, retrieved_date=today)
        console.print(f"  {len(filings)} filing rows -> {dest}", markup=False)
        for f in filings:
            if f.make and f.model and f.model_year:
                configs[(f.make, f.model, f.model_year)] = True

    console.print(f"\nResolving {len(configs)} vehicle configurations against the complaints "
                  f"database vocabulary ...", markup=False)
    resolutions, records = [], []
    for make, model, year in sorted(configs):
        resolution = complaints_src.resolve_config(make, model, year)
        resolutions.append(resolution)
        status = "ok" if resolution.resolved else "NOT QUERYABLE"
        console.print(f"  {make} {model} {year}: {status}", markup=False)
        if resolution.resolved:
            ref = complaints_src.source_ref(today)
            records.extend(complaints_src.fetch_for_config(resolution, ref))

    seen, unique = set(), []
    for r in records:
        if r.record_ref not in seen:
            seen.add(r.record_ref)
            unique.append(r)

    path = complaints_src.save_snapshot(unique, resolutions, today)
    resolved = sum(1 for r in resolutions if r.resolved)
    console.print(f"\n{len(unique)} crash-flagged independent records -> {path}", markup=False)
    console.print(f"{resolved} of {len(resolutions)} configurations were queryable.",
                  markup=False)


@cli.command()
@click.option("--report-type", type=click.Choice(["ADS", "ADAS"]), default="ADAS",
              help="Which SGO filing population to reconcile.")
@click.option("--entity", default=None, help="Limit to reporting entities matching this text.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON (disclaimers included).")
@click.option("--limit", type=int, default=0, help="Show at most N findings (0 = all).")
def reconcile(report_type: str, entity: str | None, as_json: bool, limit: int) -> None:
    """Reconcile a filing population against the independent population."""
    if not as_json:
        _scope_banner()
    try:
        report = run(report_type, _today(), entity_filter=entity)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc))

    if limit > 0:
        report.findings = report.findings[:limit]

    if as_json:
        click.echo(_json.dumps(to_json(report), indent=2))
    else:
        # markup=False: the report body is preformatted plain text; bracketed values such as
        # [confidence: LOW] must never be parsed as Rich markup.
        # soft_wrap=True: the body is already wrapped to 74 columns; letting Rich re-wrap it
        # to the terminal width breaks the alignment the caveats and field values rely on.
        console.print(render_text(report), markup=False, soft_wrap=True)


@cli.command()
@click.option("--report-type", type=click.Choice(["ADS", "ADAS"]), default="ADAS")
@click.option("--limit", type=int, default=10)
def amendments(report_type: str, limit: int) -> None:
    """List filings amended by their own filer.

    This is NOT a cross-source check and is excluded from the match rate -- it compares a
    filing against a later version of itself."""
    _scope_banner()
    from reconcile import amendments as amendments_mod
    from report.templates import render_amendment_block

    filings = sgo_src.load_filings(report_type, retrieved_date=_today())
    observations = amendments_mod.observe(sgo_src.version_groups(filings))
    console.print(f"{len(observations)} amendment transition(s) in {len(filings)} "
                  f"{report_type} filing rows.\n", markup=False)
    for obs in observations[:limit] if limit > 0 else observations:
        console.print(render_amendment_block(obs), markup=False, soft_wrap=True)
        console.print("")


@cli.command()
def sources() -> None:
    """Show the public sources, their roles, and the known coverage gaps."""
    _scope_banner()
    for source_id, meta in config.SOURCES.items():
        console.print(f"{meta['name']}", markup=False)
        console.print(f"  role: {meta['role']}", markup=False)
        console.print(f"  {meta['url']}\n", markup=False)
    console.print("KNOWN COVERAGE GAPS", markup=False)
    for gap in disclaimers.KNOWN_GAPS:
        console.print(f"  - {gap}\n", markup=False)


@cli.command()
def scope() -> None:
    """Print the tool's scope and standing framing disclaimer."""
    console.print(disclaimers.SCOPE_DISCLAIMER)
    console.print(f"\nScope: {config.MVP_SCOPE}.")
    console.print(f"Fields compared on a matched pair: {', '.join(config.COMPARED_FIELDS)}.")
    console.print("\n" + disclaimers.MATCH_RATE_INTERPRETATION)


if __name__ == "__main__":
    cli()
