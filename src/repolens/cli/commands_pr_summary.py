"""CLI: PR job summary + optional GitHub workflow annotations (Phase 6.8)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from repolens.cli.app import app, console
from repolens.pr_summary import (
    find_newest_report_json,
    render_pr_summary,
    render_workflow_annotations,
)
from repolens.schema import FindingReport


@app.command("pr-summary")
def pr_summary_cmd(
    report: Path | None = typer.Argument(
        None,
        help="FindingReport JSON (default: newest gate_review_report_*.json under --reports-dir)",
    ),
    reports_dir: Path = typer.Option(
        Path("reports"),
        "--reports-dir",
        help="Directory to search when report path omitted",
    ),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Write Markdown to this file",
    ),
    github_summary: bool = typer.Option(
        False,
        "--github-summary",
        help="Append Markdown to $GITHUB_STEP_SUMMARY when set",
    ),
    annotate: bool = typer.Option(
        False,
        "--annotate",
        help="Print GitHub ::error / ::warning workflow commands to stdout",
    ),
) -> None:
    """Render a PR-oriented summary with Critical/High suggested fixes."""
    path = report
    if path is None:
        path = find_newest_report_json(reports_dir)
        if path is None:
            console.print(
                f"[red]No gate_review_report_*.json under[/red] {reports_dir.resolve()}"
            )
            raise typer.Exit(code=2)
    if not path.is_file():
        console.print(f"[red]Report not found:[/red] {path}")
        raise typer.Exit(code=2)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        finding_report = FindingReport.model_validate(data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        console.print(f"[red]Could not load report:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    md = render_pr_summary(finding_report)

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        console.print(f"[green]Wrote[/green] {out.resolve()}")

    summary_env = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if github_summary:
        if not summary_env:
            console.print(
                "[yellow]$GITHUB_STEP_SUMMARY unset[/yellow] — printing Markdown to stdout"
            )
            typer.echo(md)
        else:
            with Path(summary_env).open("a", encoding="utf-8") as fh:
                fh.write(md)
                if not md.endswith("\n"):
                    fh.write("\n")
            console.print(f"[green]Appended[/green] PR summary → $GITHUB_STEP_SUMMARY")

    if not out and not github_summary:
        typer.echo(md)

    if annotate:
        for line in render_workflow_annotations(finding_report):
            # Must go to stdout so Actions parses workflow commands
            typer.echo(line)
