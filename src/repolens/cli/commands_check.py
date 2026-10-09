"""Cyclicity ratchet CLI (G2): ``check --diff``."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import typer

from repolens.cli.app import check_app, console
from repolens.cli.review_options import (
    option_base,
    option_baseline,
    option_check_diff,
    option_check_format,
    option_check_path,
    option_require_baseline,
)
from repolens.config import GraphConfig, load_config
from repolens.git_refs import git_available, is_safe_git_ref, resolve_diff_base
from repolens.graph import analyse_repo_graph
from repolens.graph.baseline import DEFAULT_BASELINE_PATH, load_baseline
from repolens.graph.diff_anchor import (
    anchor_ratchet_breach,
    format_github_actions_error,
)
from repolens.graph.ratchet import evaluate_ratchet
from repolens.graph.types import GraphStatus
from repolens.quality_metrics import measure_quality_metrics

# Re-export for tests that imported from this module historically.
_is_safe_git_ref = is_safe_git_ref
_git_available = git_available

_UNANCHORED_NOTE = (
    "ratchet.unanchored: could not anchor the breach to a newly added import line "
    "(no git repository, empty diff, or no matching import)"
)


def _resolve_baseline_path(
    root: Path,
    *,
    baseline: Path | None,
    baseline_path: str,
) -> Path:
    if baseline is not None:
        return baseline.resolve() if baseline.is_absolute() else (root / baseline).resolve()
    rel = baseline_path.strip() or DEFAULT_BASELINE_PATH
    candidate = Path(rel)
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _git_diff_text(*, cwd: Path, base: str | None) -> str:
    # Two call sites keep argv literals static for scanners; validate *base* first.
    if base is not None:
        if not is_safe_git_ref(base):
            return ""
        completed = subprocess.run(
            ["git", "diff", f"{base}...HEAD"],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    else:
        completed = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    if completed.returncode != 0:
        return ""
    return completed.stdout or ""


def _print_fingerprint_delta(
    *,
    added: list[list[str]],
    removed: list[list[str]],
) -> None:
    for fp in added:
        console.print(f"+ {fp}")
    for fp in removed:
        console.print(f"- {fp}")


def _maybe_anchor_breach(
    *,
    root: Path,
    cli_base: str | None,
    added_fingerprints: list[list[str]],
    message: str,
) -> bool:
    """Print path:line (and GHA ::error) when possible. Return True if anchored."""
    if not _git_available(root):
        return False
    base = resolve_diff_base(cli_base=cli_base, cwd=root)
    diff_text = _git_diff_text(cwd=root, base=base)
    if not diff_text.strip():
        return False
    anchored = anchor_ratchet_breach(
        diff_text=diff_text,
        added_fingerprints=added_fingerprints,
    )
    if anchored is None:
        return False
    path, line, _import_text = anchored
    console.print(f"{path}:{line}")
    if os.environ.get("GITHUB_ACTIONS", "").strip().lower() == "true":
        console.print(format_github_actions_error(path, line, message))
    return True


@check_app.callback(invoke_without_command=True)
def check(
    ctx: typer.Context,
    diff: bool = option_check_diff(),
    fmt: str = option_check_format(),
    path: Path = option_check_path(),
    baseline: Path | None = option_baseline(),
    require_baseline: bool = option_require_baseline(),
    base: str | None = option_base(),
) -> None:
    """Graph-only cyclicity ratchet, or Fast Brain diagnostics with --format."""
    _body_check(ctx, diff, fmt, path, baseline, require_baseline, base)


def _body_check(
    ctx: typer.Context,
    diff: bool,
    fmt: str,
    path: Path,
    baseline: Path | None,
    require_baseline: bool,
    base: str | None,
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    fmt_n = fmt.strip().lower()
    if fmt_n in {"sarif", "jsonl"}:
        _emit_diagnostics(path.resolve(), fmt_n)
        return
    if fmt_n:
        console.print("[red]--format must be sarif | jsonl[/red]")
        raise typer.Exit(code=2)
    if not diff:
        console.print(
            "[red]Specify --diff to run the cyclicity ratchet check.[/red] "
            "Example: [cyan]repolens check --diff[/cyan]"
        )
        raise typer.Exit(code=2)
    _run_check_ratchet(path.resolve(), baseline, require_baseline, base)


def _run_check_ratchet(
    root: Path,
    baseline: Path | None,
    require_baseline: bool,
    base: str | None,
) -> None:
    cfg = load_config(root)
    graph_cfg: GraphConfig = cfg.graph
    target = _resolve_baseline_path(
        root, baseline=baseline, baseline_path=graph_cfg.baseline_path
    )
    must_have = require_baseline or graph_cfg.require_baseline
    if not target.is_file():
        if must_have:
            console.print(f"[red]No baseline found at[/red] {target}")
            console.print("Run [cyan]repolens baseline set[/cyan] to create one.")
            raise typer.Exit(code=2)
        console.print(
            f"[yellow]Warning:[/yellow] no baseline found at {target}; "
            "skipping ratchet check. Run [cyan]repolens baseline set[/cyan] to create one."
        )
        raise typer.Exit(code=0)

    result = analyse_repo_graph(root, config=graph_cfg)
    if result.status is GraphStatus.FAILED:
        for gap in result.durability_gaps:
            console.print(f"[red]{gap}[/red]")
        console.print("[red]Graph analysis failed; ratchet check aborted.[/red]")
        raise typer.Exit(code=3)
    if result.status is GraphStatus.SKIPPED:
        for gap in result.durability_gaps:
            console.print(f"[red]{gap}[/red]")
        console.print(
            "[red]Graph analysis was skipped (e.g. graph disabled); "
            "ratchet check aborted.[/red]"
        )
        raise typer.Exit(code=3)

    doc = load_baseline(target)
    current_metrics = measure_quality_metrics(root, cfg, result)
    ratchet = evaluate_ratchet(
        current=result, baseline=doc, config=graph_cfg, current_metrics=current_metrics,
    )
    console.print(ratchet.message)
    _print_fingerprint_delta(
        added=ratchet.fingerprints_added, removed=ratchet.fingerprints_removed,
    )
    for note in ratchet.notes:
        console.print(f"[yellow]{note}[/yellow]")
    if ratchet.config_mismatch and ratchet.config_mismatch_detail:
        console.print(f"[dim]Config drift: {ratchet.config_mismatch_detail}[/dim]")
    if ratchet.breached:
        if not _maybe_anchor_breach(
            root=root, cli_base=base,
            added_fingerprints=ratchet.fingerprints_added, message=ratchet.message,
        ):
            console.print(f"[yellow]{_UNANCHORED_NOTE}[/yellow]")
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)


def _emit_diagnostics(root: Path, fmt: str) -> None:
    import json

    from repolens.config import load_config
    from repolens.diagnostics import (
        collect_fast_issues,
        diagnostic_jsonl,
        diagnostic_sarif,
    )

    cfg = load_config(root)
    issues = collect_fast_issues(root, cfg)
    if fmt == "jsonl":
        typer.echo(diagnostic_jsonl(issues), nl=False)
    else:
        typer.echo(json.dumps(diagnostic_sarif(issues, root=root), indent=2))
    raise typer.Exit(code=1 if issues else 0)
