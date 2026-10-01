"""CLI: ``repolens diff-audit`` — resolve / new / debt drift between two reports."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.table import Table

from repolens.cli.app import app, console
from repolens.diff_audit import diff_audit_as_dict, diff_audit_files


@app.command("diff-audit")
def diff_audit_cmd(
    left: Path = typer.Argument(..., exists=True, readable=True, help="Earlier FindingReport JSON"),
    right: Path = typer.Argument(..., exists=True, readable=True, help="Later FindingReport JSON"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON"),
) -> None:
    """Compare two audit JSON reports: resolved, new, and confidence drift."""
    try:
        result = diff_audit_files(left, right)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        console.print(f"[red]diff-audit failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if as_json:
        typer.echo(json.dumps(diff_audit_as_dict(result), indent=2))
        return

    table = Table(title="diff-audit")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Left", str(left))
    table.add_row("Right", str(right))
    table.add_row("Resolved", str(len(result.resolved)))
    table.add_row("New", str(len(result.new)))
    table.add_row("Unchanged", str(result.unchanged))
    table.add_row(
        "Confidence",
        f"{result.left_confidence}% → {result.right_confidence}% "
        f"(Δ {result.confidence_delta:+d})",
    )
    console.print(table)
    for note in result.notes:
        console.print(f"[yellow]{note}[/yellow]")
    if result.new[:10]:
        console.print("[bold]New[/bold]")
        for row in result.new[:10]:
            console.print(f"  + {row}")
    if result.resolved[:10]:
        console.print("[bold]Resolved[/bold]")
        for row in result.resolved[:10]:
            console.print(f"  - {row}")
