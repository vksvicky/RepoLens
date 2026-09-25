"""Cyclicity ratchet CLI (G2): ``check --diff``."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import typer

from repolens.cli.app import check_app, console
from repolens.config import GraphConfig, load_config
from repolens.graph import analyse_python_graph
from repolens.graph.baseline import DEFAULT_BASELINE_PATH, load_baseline
from repolens.graph.diff_anchor import (
    anchor_ratchet_breach,
    format_github_actions_error,
)
from repolens.graph.ratchet import evaluate_ratchet
from repolens.graph.types import GraphStatus

_MERGE_BASE_CANDIDATES = ("origin/main", "origin/master", "main", "master")

# Allow common git refs / SHAs; reject option-injection and shell metacharacters.
_SAFE_GIT_REF = re.compile(r"^(?:HEAD(?:~\d+)?|[A-Za-z0-9][A-Za-z0-9._/\-^{}]*)$")

_UNANCHORED_NOTE = (
    "ratchet.unanchored: could not anchor the breach to a newly added import line "
    "(no git repository, empty diff, or no matching import)"
)


def _is_safe_git_ref(ref: str) -> bool:
    """Return True when *ref* is safe to pass as a git argv token (no shell)."""
    if not ref or len(ref) > 256 or ref.startswith("-"):
        return False
    return _SAFE_GIT_REF.fullmatch(ref) is not None


def resolve_diff_base(*, cli_base: str | None, cwd: Path | None = None) -> str | None:
    """Resolve git diff base for ratchet anchoring.

    Priority: CLI ``--base`` → ``GITHUB_BASE_REF`` → merge-base heuristic → None
    (working-tree / ``git diff HEAD`` fallback).
    """
    if cli_base:
        return cli_base if _is_safe_git_ref(cli_base) else None
    gha = os.environ.get("GITHUB_BASE_REF", "").strip()
    if gha:
        candidate = gha if gha.startswith("origin/") else f"origin/{gha}"
        return candidate if _is_safe_git_ref(candidate) else None

    root = cwd or Path.cwd()
    for ref in _MERGE_BASE_CANDIDATES:
        completed = subprocess.run(
            ["git", "merge-base", "HEAD", ref],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        sha = (completed.stdout or "").strip()
        if completed.returncode == 0 and sha and _is_safe_git_ref(sha):
            return sha

    parent = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD~1"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if parent.returncode == 0 and (parent.stdout or "").strip():
        return "HEAD~1"
    return None


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


def _git_available(cwd: Path) -> bool:
    if shutil.which("git") is None:
        return False
    completed = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and (completed.stdout or "").strip() == "true"


def _git_diff_text(*, cwd: Path, base: str | None) -> str:
    # Two call sites keep argv literals static for scanners; validate *base* first.
    if base is not None:
        if not _is_safe_git_ref(base):
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
    diff: bool = typer.Option(
        False,
        "--diff",
        help="Compare runtime cyclicity to the baseline (graph-only ratchet)",
    ),
    path: Path = typer.Option(Path("."), "--path", help="Project root to analyse"),
    baseline: Path | None = typer.Option(
        None,
        "--baseline",
        help="Baseline JSON path (default: config baseline_path or .repolens/baseline.json)",
    ),
    require_baseline: bool = typer.Option(
        False,
        "--require-baseline",
        help="Exit 2 when no baseline file is present (recommended for CI)",
    ),
    base: str | None = typer.Option(
        None,
        "--base",
        help="Git diff base ref (else GITHUB_BASE_REF / merge-base / working tree)",
    ),
) -> None:
    """Graph-only cyclicity ratchet check for CI and pre-commit."""
    if ctx.invoked_subcommand is not None:
        return
    if not diff:
        console.print(
            "[red]Specify --diff to run the cyclicity ratchet check.[/red] "
            "Example: [cyan]repolens check --diff[/cyan]"
        )
        raise typer.Exit(code=2)

    root = path.resolve()
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

    result = analyse_python_graph(root, config=graph_cfg)
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
    ratchet = evaluate_ratchet(current=result, baseline=doc, config=graph_cfg)
    console.print(ratchet.message)
    _print_fingerprint_delta(
        added=ratchet.fingerprints_added,
        removed=ratchet.fingerprints_removed,
    )
    for note in ratchet.notes:
        console.print(f"[yellow]{note}[/yellow]")
    if ratchet.config_mismatch and ratchet.config_mismatch_detail:
        console.print(f"[dim]Config drift: {ratchet.config_mismatch_detail}[/dim]")

    if ratchet.breached:
        if not _maybe_anchor_breach(
            root=root,
            cli_base=base,
            added_fingerprints=ratchet.fingerprints_added,
            message=ratchet.message,
        ):
            console.print(f"[yellow]{_UNANCHORED_NOTE}[/yellow]")
        raise typer.Exit(code=1)
    raise typer.Exit(code=0)
