"""CLI: score supporting actionability metrics from a FindingReport JSON."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.table import Table

from repolens.benchmark import score_actionability_file
from repolens.cli.app import app, console


@app.command("score-report")
def score_report_cmd(
    report: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="FindingReport JSON path (e.g. reports/*.json)",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON instead of a table",
    ),
) -> None:
    """Score supporting actionability metrics (Phase 6.6). Not remediation rate/MTTR."""
    try:
        scores = score_actionability_file(report)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        console.print(f"[red]Could not score report:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if as_json:
        typer.echo(json.dumps(scores.as_dict(), indent=2))
        return

    table = Table(title="Supporting actionability (not remediation study)")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Report", str(report.resolve()))
    table.add_row("Total issues", str(scores.total_issues))
    table.add_row("With codeExample", str(scores.issues_with_code_example))
    readiness = (
        f"{scores.suggested_fix_readiness:.0%}"
        if scores.suggested_fix_readiness is not None
        else "n/a"
    )
    table.add_row("Suggested-fix readiness", readiness)
    table.add_row(
        "Critical/High with example",
        f"{scores.critical_high_with_code_example}/{scores.critical_high}",
    )
    table.add_row(
        "Medium/Low with example",
        f"{scores.medium_low_with_code_example}/{scores.medium_low}",
    )
    table.add_row(
        "Sources (scanner/llm/heuristic)",
        f"{scores.scanner_sourced}/{scores.llm_sourced}/{scores.heuristic_sourced}",
    )
    table.add_row(
        "Location verified/unverified",
        f"{scores.location_verified}/{scores.location_unverified}",
    )
    console.print(table)
    console.print(
        "[dim]Headline remediation rate / MTTR require the human study in "
        "docs/benchmarks/methodology.md[/dim]"
    )
