"""CLI: ``repolens diff-audit`` — resolve / new / debt drift between two reports."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.table import Table

from repolens.cli.app import app, console
from repolens.diff_audit import (
    diff_audit_as_dict,
    diff_audit_files,
    load_report,
    render_diff_audit_html,
    render_diff_audit_md,
)


@app.command("diff-audit")
def diff_audit_cmd(
    left: Path = typer.Argument(..., exists=True, readable=True, help="Earlier FindingReport JSON"),
    right: Path = typer.Argument(..., exists=True, readable=True, help="Later FindingReport JSON"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON"),
    fmt: str = typer.Option(
        "table",
        "--format",
        help="table | md | html (client one-pager); use --out to write a file",
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Write Markdown/HTML comparison to this path"
    ),
) -> None:
    """Compare two audit JSON reports: resolved, new, and confidence drift."""
    try:
        result = diff_audit_files(left, right)
        left_rep = load_report(left)
        right_rep = load_report(right)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        console.print(f"[red]diff-audit failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    fmt_norm = fmt.strip().lower()
    if as_json or fmt_norm == "json":
        typer.echo(json.dumps(diff_audit_as_dict(result), indent=2))
        return

    if fmt_norm in {"md", "markdown", "html"}:
        body = (
            render_diff_audit_html(result, left=left_rep, right=right_rep)
            if fmt_norm == "html"
            else render_diff_audit_md(result, left=left_rep, right=right_rep)
        )
        if out is not None:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(body, encoding="utf-8")
            console.print(f"[green]Wrote[/green] {out}")
        else:
            typer.echo(body)
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
