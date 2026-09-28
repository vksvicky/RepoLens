"""CLI: PR job summary + optional GitHub workflow annotations (Phase 6.8 + #29)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from repolens.cli.app import app, console
from repolens.github_pr_comments import (
    post_or_update_review_comments,
    resolve_github_token,
    resolve_pr_number,
    resolve_repo_slug,
)
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
    post_review_comments: bool = typer.Option(
        False,
        "--post-review-comments",
        help=(
            "Opt-in: post/update up to 3 Critical/High inline PR review comments "
            "(idempotent markers; needs GITHUB_TOKEN + pull_request context)"
        ),
    ),
    pr: int | None = typer.Option(
        None,
        "--pr",
        help="Pull request number (default: GITHUB_EVENT_PATH pull_request.number)",
    ),
) -> None:
    """Render a PR-oriented summary with Critical/High suggested fixes."""
    finding_report = _load_finding_report(report, reports_dir)
    md = render_pr_summary(finding_report)
    _emit_pr_summary(md, out=out, github_summary=github_summary)
    if annotate:
        for line in render_workflow_annotations(finding_report):
            # Must go to stdout so Actions parses workflow commands
            typer.echo(line)
    if post_review_comments:
        _post_pr_review_comments(finding_report, pr=pr)


def _load_finding_report(report: Path | None, reports_dir: Path) -> FindingReport:
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
        return FindingReport.model_validate(data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        console.print(f"[red]Could not load report:[/red] {exc}")
        raise typer.Exit(code=2) from exc


def _append_github_summary(md: str, summary_env: str) -> None:
    with Path(summary_env).open("a", encoding="utf-8") as handle:
        handle.write(md)
        if not md.endswith("\n"):
            handle.write("\n")
    console.print("[green]Appended[/green] PR summary → $GITHUB_STEP_SUMMARY")


def _emit_pr_summary(md: str, *, out: Path | None, github_summary: bool) -> None:
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        console.print(f"[green]Wrote[/green] {out.resolve()}")
    summary_env = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if github_summary and not summary_env:
        console.print(
            "[yellow]$GITHUB_STEP_SUMMARY unset[/yellow] — printing Markdown to stdout"
        )
        typer.echo(md)
    elif github_summary:
        _append_github_summary(md, summary_env)
    if not out and not github_summary:
        typer.echo(md)


def _post_pr_review_comments(finding_report: FindingReport, *, pr: int | None) -> None:
    token = resolve_github_token()
    slug = resolve_repo_slug()
    pr_number = resolve_pr_number(explicit=pr)
    if not token:
        console.print(
            "[yellow]--post-review-comments ignored:[/yellow] no GITHUB_TOKEN/GH_TOKEN"
        )
        return
    if slug is None:
        console.print(
            "[yellow]--post-review-comments ignored:[/yellow] GITHUB_REPOSITORY unset"
        )
        return
    if pr_number is None:
        console.print(
            "[yellow]--post-review-comments ignored:[/yellow] "
            "pass --pr or run on a pull_request event"
        )
        return
    owner, repo = slug
    result = post_or_update_review_comments(
        finding_report,
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        token=token,
    )
    console.print(
        f"[green]PR comments[/green] created={result.created} "
        f"updated={result.updated} skipped={result.skipped}"
    )
    for err in result.errors[:5]:
        console.print(f"[dim]{err}[/dim]")
