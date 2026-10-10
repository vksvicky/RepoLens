"""``repolens fix`` — emit or apply a grounded single-file remediation patch."""

from __future__ import annotations

from pathlib import Path

import typer

from repolens.cli.app import app, console
from repolens.cli.pack_scope import option_path
from repolens.cli.review_options import option_out
from repolens.explain import IssueNotFoundError, find_issue, load_latest_report
from repolens.fix_apply import FixRefuseError, apply_fix, build_unified_diff, plan_fix


@app.command("fix")
def fix_cmd(
    fingerprint: str = typer.Argument(
        ..., help="Finding fingerprint (stableId) or occurrence id from a gate report"
    ),
    path: str | None = option_path(),
    out: Path | None = option_out(),
    patch: bool = typer.Option(
        False, "--patch", help="Print unified diff to stdout (do not write files)"
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Show diff then apply on disk (use --yes to skip confirm)",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Apply without confirmation (with --interactive)"
    ),
) -> None:
    """Apply one grounded remediation from a report. Single file only — no self-heal loops."""
    if patch and interactive:
        console.print("[red]Choose one of --patch or --interactive[/red]")
        raise typer.Exit(code=2)
    if not patch and not interactive:
        console.print(
            "[red]Specify --patch (stdout diff) or --interactive (apply on disk)[/red]"
        )
        raise typer.Exit(code=2)

    root = Path(path or ".").resolve()
    try:
        report, report_path = load_latest_report(root, out_dir=out)
        issue = find_issue(report, fingerprint)
        fix_plan = plan_fix(root, issue)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    except IssueNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    except FixRefuseError as exc:
        console.print(f"[yellow]Refused:[/yellow] {exc}")
        raise typer.Exit(code=2) from exc

    console.print(f"[dim]report[/dim] {report_path}")
    console.print(f"[dim]finding[/dim] {issue.title} → {fix_plan.relative_path}")
    diff = build_unified_diff(fix_plan)
    if not diff.strip():
        console.print("[yellow]Empty diff — file already matches After snippet.[/yellow]")
        raise typer.Exit(code=0)

    if patch:
        typer.echo(diff, nl=False)
        return

    # interactive
    typer.echo(diff, nl=False)
    if not yes:
        confirm = typer.confirm("Apply this patch on disk?", default=False)
        if not confirm:
            console.print("Aborted.")
            raise typer.Exit(code=0)
    try:
        apply_fix(fix_plan)
    except FixRefuseError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    console.print(f"[green]Applied[/green] {fix_plan.relative_path} (syntax OK)")
