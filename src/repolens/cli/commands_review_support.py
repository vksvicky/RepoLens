"""Ratchet and error mapping for ``repolens review``."""

from __future__ import annotations

from pathlib import Path

import typer

from repolens.cli.app import console
from repolens.cli.commands_check import _print_fingerprint_delta, _resolve_baseline_path
from repolens.config import load_config
from repolens.graph import analyse_repo_graph
from repolens.graph.baseline import load_baseline
from repolens.graph.ratchet import evaluate_ratchet
from repolens.graph.types import GraphStatus
from repolens.llm import LlmError
from repolens.pipeline import ScannerRequirementError
from repolens.quality_metrics import measure_quality_metrics
from repolens.sarif_import import SarifImportError


def _ratchet_breached_for_review(root: Path, *, ratchet_flag: bool) -> bool:
    """Run cyclicity ratchet when ``--ratchet`` or ``[graph].ratchet`` is set.

    Caller must invoke only for ``mode == \"review\"``; sentinel/architecture must not
    inherit config ratchet via shared ``_run_mode``.

    Missing baseline soft-skips unless ``require_baseline`` (same as ``check --diff``).
    Graph FAILED/SKIPPED aborts with exit 3. Returns True when cyclicity increased.
    """
    cfg = load_config(root)
    graph_cfg = cfg.graph
    if not (ratchet_flag or graph_cfg.ratchet):
        return False

    target = _resolve_baseline_path(
        root, baseline=None, baseline_path=graph_cfg.baseline_path
    )
    must_have = graph_cfg.require_baseline
    if not target.is_file():
        if must_have:
            console.print(f"[red]No baseline found at[/red] {target}")
            console.print("Run [cyan]repolens baseline set[/cyan] to create one.")
            raise typer.Exit(code=2)
        console.print(
            f"[yellow]Warning:[/yellow] no baseline found at {target}; "
            "skipping ratchet check. Run [cyan]repolens baseline set[/cyan] to create one."
        )
        return False

    gres = analyse_repo_graph(root, config=graph_cfg)
    if gres.status is GraphStatus.FAILED:
        for gap in gres.durability_gaps:
            console.print(f"[red]{gap}[/red]")
        console.print("[red]Graph analysis failed; ratchet check aborted.[/red]")
        raise typer.Exit(code=3)
    if gres.status is GraphStatus.SKIPPED:
        for gap in gres.durability_gaps:
            console.print(f"[red]{gap}[/red]")
        console.print(
            "[red]Graph analysis was skipped (e.g. graph disabled); "
            "ratchet check aborted.[/red]"
        )
        raise typer.Exit(code=3)

    doc = load_baseline(target)
    current_metrics = measure_quality_metrics(root, cfg, gres)
    ratchet = evaluate_ratchet(
        current=gres,
        baseline=doc,
        config=graph_cfg,
        current_metrics=current_metrics,
    )
    console.print(ratchet.message)
    _print_fingerprint_delta(
        added=ratchet.fingerprints_added,
        removed=ratchet.fingerprints_removed,
    )
    for note in ratchet.notes:
        console.print(f"[yellow]{note}[/yellow]")
    if ratchet.config_mismatch and ratchet.config_mismatch_detail:
        console.print(f"[dim]Config drift: {ratchet.config_mismatch_detail}[/dim]")
    return ratchet.breached



def _map_run_mode_error(exc: BaseException) -> None:
    """Turn known review failures into typer exits. Unknown errors propagate."""
    if isinstance(exc, FileNotFoundError):
        console.print(f"[red]Config/source error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    if isinstance(exc, ValueError):
        console.print(f"[red]Config/usage error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    if isinstance(exc, ScannerRequirementError):
        console.print(f"[red]{exc}[/red]")
        console.print(
            "Install with [cyan]repolens plugins install[/cyan] or see docs/scanners.md"
        )
        raise typer.Exit(code=2) from exc
    if isinstance(exc, SarifImportError):
        console.print(f"[red]SARIF import:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    if isinstance(exc, LlmError):
        from repolens.llm import provider_setup_hints

        console.print(f"[red]Model error:[/red] {exc}")
        msg = str(exc).lower()
        if "no model provider" in msg or "missing api key" in msg:
            for line in provider_setup_hints():
                console.print(f"[yellow]→[/yellow] {line}")
        elif "timed out" in msg:
            console.print(
                "[yellow]→[/yellow] Tip: [cyan]--timeout 1800[/cyan], "
                "[cyan]--mode diff --since HEAD~20[/cyan], or "
                "[cyan]--scanners-only[/cyan] / [cyan]--dry-run[/cyan] first."
            )
        else:
            console.print(
                "Run [cyan]repolens init[/cyan] or see docs/setup-ai-and-scanners.md"
            )
        raise typer.Exit(code=4) from exc
    if isinstance(exc, RuntimeError):
        console.print(f"[red]Source error:[/red] {exc}")
        raise typer.Exit(code=3) from None
