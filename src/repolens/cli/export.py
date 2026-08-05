"""Report export and summary table helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer
from rich.table import Table

from repolens.cli.app import app, console
from repolens.schema import FindingReport

@app.command()
def export(
    report: Path = typer.Argument(..., exists=True, readable=True, help="Markdown report path"),
    pdf: bool = typer.Option(False, "--pdf", help="Convert with pandoc if available"),
) -> None:
    """Export or convert an existing report."""
    typer.echo(f"Report: {report.resolve()}")
    if not pdf:
        return
    pandoc = shutil.which("pandoc")
    if not pandoc:
        console.print(
            "[yellow]pandoc not found.[/yellow] Install pandoc or use Print → Save as PDF."
        )
        raise typer.Exit(code=2)
    out = report.with_suffix(".pdf")
    completed = subprocess.run([pandoc, str(report), "-o", str(out)], check=False)
    if completed.returncode != 0:
        console.print("[red]pandoc failed[/red]")
        raise typer.Exit(code=2)
    console.print(f"[green]PDF:[/green] {out}")


def _print_summary(confidence: int, files: int, report: FindingReport, *, dry_run: bool) -> None:
    from repolens.report import format_duration

    table = Table(title="RepoLens summary")
    table.add_column("Metric")
    table.add_column("Value")
    if dry_run:
        table.add_row("Dry run", "yes")
    table.add_row("Files scanned", str(files))
    table.add_row("Gate confidence", f"{confidence}%")
    if report.securityAuditConfidence is not None:
        table.add_row("Security audit", f"{report.securityAuditConfidence}%")
    if report.architectureAuditConfidence is not None:
        table.add_row("Architecture audit", f"{report.architectureAuditConfidence}%")
    duration = format_duration(report.durationSeconds)
    if duration is not None:
        table.add_row("Duration", duration)
    if report.llmReusedFrom:
        table.add_row("LLM", f"reused from {report.llmReusedFrom}")
    elif report.llmSkipped:
        table.add_row("LLM", "skipped (no file delta; no prior snapshot)")
    table.add_row("Critical", str(report.summary.critical))
    table.add_row("High", str(report.summary.high))
    table.add_row("Medium", str(report.summary.medium))
    table.add_row("Low", str(report.summary.low))
    if report.scannerRuns:
        ran = sum(1 for r in report.scannerRuns if r.status == "ran")
        table.add_row("Scanners ran", f"{ran}/{len(report.scannerRuns)}")
    console.print(table)
