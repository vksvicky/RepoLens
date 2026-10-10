"""Report export and summary table helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer
from rich.table import Table

from repolens.cli.app import app, console
from repolens.evidence_pack import build_evidence_pack, resolve_evidence_inputs
from repolens.executive_summary import write_executive_summary
from repolens.schema import FindingReport


@app.command()
def export(
    report: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Markdown/JSON report path, or a reports directory (with --evidence-pack)",
    ),
    pdf: bool = typer.Option(False, "--pdf", help="Convert with pandoc if available"),
    evidence_pack: bool = typer.Option(
        False,
        "--evidence-pack",
        help="Write a timestamped M&A zip (Markdown, JSON, SARIF, SBOM, provenance)",
    ),
    executive_summary: bool = typer.Option(
        False,
        "--executive-summary",
        help="Write a 2-page board summary (Markdown; use --format html for HTML)",
    ),
    fmt: str = typer.Option(
        "md",
        "--format",
        help="md | html for --executive-summary (default md)",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Output directory for pack/summary (default: next to the report)",
    ),
) -> None:
    """Export or convert an existing report."""
    typer.echo(f"Report: {report.resolve()}")
    if evidence_pack and executive_summary:
        console.print("[red]Choose one of --evidence-pack or --executive-summary[/red]")
        raise typer.Exit(code=2)
    dest = out or (report.resolve() if report.is_dir() else report.resolve().parent)
    if evidence_pack:
        try:
            zip_path = build_evidence_pack(report, dest)
        except (OSError, FileNotFoundError, ValueError) as exc:
            console.print(f"[red]evidence pack failed:[/red] {exc}")
            raise typer.Exit(code=2) from exc
        console.print(f"[green]Evidence pack:[/green] {zip_path}")
        return
    if executive_summary:
        fmt_norm = fmt.strip().lower()
        if fmt_norm not in {"md", "html"}:
            console.print("[red]--format must be md or html[/red]")
            raise typer.Exit(code=2)
        try:
            inputs = resolve_evidence_inputs(report)
            path = write_executive_summary(inputs.report, dest, fmt=fmt_norm)
        except (OSError, FileNotFoundError, ValueError) as exc:
            console.print(f"[red]executive summary failed:[/red] {exc}")
            raise typer.Exit(code=2) from exc
        console.print(f"[green]Executive summary:[/green] {path}")
        if pdf:
            _pandoc_pdf(path)
        return
    if not pdf:
        return
    _pandoc_pdf(report)


def _pandoc_pdf(report: Path) -> None:
    pandoc = shutil.which("pandoc")
    if not pandoc:
        console.print(
            "[yellow]pandoc not found.[/yellow] Install pandoc or use Print → Save as PDF."
        )
        raise typer.Exit(code=2)
    pdf_out = report.with_suffix(".pdf")
    completed = subprocess.run([pandoc, str(report), "-o", str(pdf_out)], check=False)
    if completed.returncode != 0:
        console.print("[red]pandoc failed[/red]")
        raise typer.Exit(code=2)
    console.print(f"[green]PDF:[/green] {pdf_out}")


def llm_status_label(report: FindingReport) -> str | None:
    """Short LLM row for the CLI summary table (Phase 6.3 triage-aware)."""
    if report.llmReusedFrom:
        return f"reused from {report.llmReusedFrom}"
    if report.llmBypassed:
        return "bypassed (scanners clean at triage floor)"
    if report.llmSkipped:
        return "skipped (no file delta; no prior snapshot)"
    return None


def _print_gate_and_ai_blocks(report: FindingReport) -> None:
    """Deterministic gate and AI deep audit, kept visually separate."""
    from rich.markup import escape

    from repolens.report_blocks import ai_audit_lines, deterministic_gate_lines

    for head, detail in (deterministic_gate_lines(report), ai_audit_lines(report)):
        console.print(f"[bold]{escape(head)}[/bold]")
        console.print(escape(detail))


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
        table.add_row("Critical/High rows", collapsed)
    table.add_row("Critical", str(report.summary.critical))
    table.add_row("High", str(report.summary.high))
    table.add_row("Medium", str(report.summary.medium))
    table.add_row("Low", str(report.summary.low))
    if report.suppressedIssues:
        from repolens.report_metrics import suppression_suffix

        table.add_row(
            "Suppressed",
            f"{len(report.suppressedIssues)}{suppression_suffix(report)}",
        )
    if report.scannerRuns:
        ran = sum(1 for r in report.scannerRuns if r.status == "ran")
        table.add_row("Scanners ran", f"{ran}/{len(report.scannerRuns)}")
    headline = format_two_lane_headline(report)
    if headline:
        console.print(f"[bold]Two-Lane[/bold]: {headline}")
    console.print(table)
    _print_gate_and_ai_blocks(report)
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
