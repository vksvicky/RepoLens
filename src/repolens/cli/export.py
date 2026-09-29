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


def llm_status_label(report: FindingReport) -> str | None:
    """Short LLM row for the CLI summary table (Phase 6.3 triage-aware)."""
    if report.llmReusedFrom:
        return f"reused from {report.llmReusedFrom}"
    if report.llmBypassed:
        return "bypassed (scanners clean at triage floor)"
    if report.llmSkipped:
        return "skipped (no file delta; no prior snapshot)"
    return None


def _print_summary(confidence: int, files: int, report: FindingReport, *, dry_run: bool) -> None:
    from repolens.metrics import low_audit_brief
    from repolens.report import (
        GATE_ADEQUACY_ONE_LINER,
        format_collapsed_duplicates,
        format_duration,
        format_two_lane_headline,
    )

    table = Table(title="RepoLens summary")
    table.add_column("Metric")
    table.add_column("Value")
    if dry_run:
        table.add_row("Dry run", "yes")
    prov = report.provenance
    fb = prov.fastBrainFiles if prov is not None else None
    llm = prov.llmPackFiles if prov is not None else None
    if fb is not None:
        table.add_row("Files scanned (Fast Brain)", str(fb))
        if llm is not None:
            table.add_row("LLM pack files", str(llm))
    else:
        table.add_row("Files scanned", str(files))
    table.add_row("Gate confidence", f"{confidence}%")
    if report.securityAuditConfidence is not None:
        table.add_row("Security audit", f"{report.securityAuditConfidence}%")
    if report.reliabilityAuditConfidence is not None:
        table.add_row("Reliability audit", f"{report.reliabilityAuditConfidence}%")
    if report.architectureAuditConfidence is not None:
        table.add_row("Architecture audit", f"{report.architectureAuditConfidence}%")
    duration = format_duration(report.durationSeconds)
    if duration is not None:
        table.add_row("Duration", duration)
    llm_label = llm_status_label(report)
    if llm_label is not None:
        table.add_row("LLM", llm_label)
    collapsed = format_collapsed_duplicates(report)
    if collapsed is not None:
        table.add_row("Duplicates merged", collapsed)
    table.add_row("Critical", str(report.summary.critical))
    table.add_row("High", str(report.summary.high))
    table.add_row("Medium", str(report.summary.medium))
    table.add_row("Low", str(report.summary.low))
    if report.scannerRuns:
        ran = sum(1 for r in report.scannerRuns if r.status == "ran")
        table.add_row("Scanners ran", f"{ran}/{len(report.scannerRuns)}")
    headline = format_two_lane_headline(report)
    if headline:
        console.print(f"[bold]Two-Lane[/bold]: {headline}")
    console.print(table)
    notes = list(report.scoreNotes) or low_audit_brief(report)
    for reason in notes:
        console.print(reason)
    cov = report.coverage
    if cov is not None and cov.missed:
        from repolens.coverage import explain_missed_id

        console.print("Questions the review did not finish:")
        for cid in cov.missed:
            sentence = cov.missedNotes.get(cid) or explain_missed_id(
                cid, report.durabilityGaps
            )
            console.print(f"- {sentence}")
    console.print(f"* {GATE_ADEQUACY_ONE_LINER}")
