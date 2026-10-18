"""Ratchet, flag checks, and run-mode helpers for ``repolens review``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from repolens.cli.app import _coerce_local_path, console
from repolens.cli.commands_check import _print_fingerprint_delta, _resolve_baseline_path
from repolens.cli.exit_codes import EXIT_BAD_INPUT, EXIT_NOT_READY
from repolens.cli.export import _print_summary
from repolens.cli.run_request import RunRequest
from repolens.config import load_config
from repolens.graph import analyse_repo_graph
from repolens.graph.baseline import load_baseline
from repolens.graph.ratchet import evaluate_ratchet
from repolens.graph.types import GraphStatus
from repolens.llm import LlmError
from repolens.pipeline import ReviewRun, ScannerRequirementError, fail_on_triggered, run_review
from repolens.quality_metrics import measure_quality_metrics
from repolens.sarif_import import SarifImportError
from repolens.sources import SourceError, resolve_source, select_source


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

    target = _resolve_baseline_path(root, baseline=None, baseline_path=graph_cfg.baseline_path)
    must_have = graph_cfg.require_baseline
    if not target.is_file():
        if must_have:
            console.print(f"[red]No baseline found at[/red] {target}")
            console.print("Run [cyan]repolens baseline set[/cyan] to create one.")
            raise typer.Exit(code=EXIT_BAD_INPUT)
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
        raise typer.Exit(code=EXIT_NOT_READY)
    if gres.status is GraphStatus.SKIPPED:
        for gap in gres.durability_gaps:
            console.print(f"[red]{gap}[/red]")
        console.print(
            "[red]Graph analysis was skipped (e.g. graph disabled); ratchet check aborted.[/red]"
        )
        raise typer.Exit(code=EXIT_NOT_READY)

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
        raise typer.Exit(code=EXIT_BAD_INPUT) from exc
    if isinstance(exc, ValueError):
        console.print(f"[red]Config/usage error:[/red] {exc}")
        raise typer.Exit(code=EXIT_BAD_INPUT) from exc
    if isinstance(exc, ScannerRequirementError):
        console.print(f"[red]{exc}[/red]")
        console.print("Install with [cyan]repolens plugins install[/cyan] or see docs/scanners.md")
        raise typer.Exit(code=EXIT_BAD_INPUT) from exc
    if isinstance(exc, SarifImportError):
        console.print(f"[red]SARIF import:[/red] {exc}")
        raise typer.Exit(code=EXIT_BAD_INPUT) from exc
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
            console.print("Run [cyan]repolens init[/cyan] or see docs/setup-ai-and-scanners.md")
        raise typer.Exit(code=4) from exc
    if isinstance(exc, RuntimeError):
        console.print(f"[red]Source error:[/red] {exc}")
        raise typer.Exit(code=EXIT_NOT_READY) from None


def _reject_run_flags(request: RunRequest) -> None:
    if request.fmt not in {"md", "json", "both"}:
        console.print("[red]--format must be md | json | both[/red]")
        raise typer.Exit(code=EXIT_BAD_INPUT)
    if request.require_sarif_import and not request.import_sarif:
        console.print("[red]--require-sarif-import needs at least one --import-sarif path[/red]")
        raise typer.Exit(code=EXIT_BAD_INPUT)
    if request.scanners_only and request.dry_run:
        console.print("[red]--scanners-only cannot be combined with --dry-run[/red]")
        raise typer.Exit(code=EXIT_BAD_INPUT)
    if request.force_full and request.force_changed:
        console.print("[red]--full and --changed cannot be combined[/red]")
        raise typer.Exit(code=EXIT_BAD_INPUT)
    if request.git_diff is not None and request.force_full:
        console.print("[red]--full and --git-diff cannot be combined[/red]")
        raise typer.Exit(code=EXIT_BAD_INPUT)
    if request.git_diff is not None and request.force_changed:
        console.print("[red]--changed and --git-diff cannot be combined[/red]")
        raise typer.Exit(code=EXIT_BAD_INPUT)
    if request.deep_passes is not None and request.deep_passes < 1:
        console.print("[red]--deep-passes must be >= 1[/red]")
        raise typer.Exit(code=EXIT_BAD_INPUT)
    if request.quiet and request.verbose:
        console.print("[red]--quiet and --verbose cannot be combined[/red]")
        raise typer.Exit(code=EXIT_BAD_INPUT)
    if request.model_lock is True and request.no_model_lock:
        console.print("[red]--model-lock and --no-model-lock cannot be combined[/red]")
        raise typer.Exit(code=EXIT_BAD_INPUT)


def _resolve_run_source(
    *,
    path: str | Path | None,
    git_url: str | None,
    github: str | None,
    bitbucket: str | None,
    hf: str | None,
    ref: str | None,
) -> Any:
    try:
        local_path = _coerce_local_path(path)
        kind, value = select_source(
            path=local_path,
            git_url=git_url,
            github=github,
            bitbucket=bitbucket,
            hf=hf,
        )
        return resolve_source(kind=kind, value=value, ref=ref)
    except SourceError as exc:
        msg = str(exc)
        code = 3 if msg.startswith("Clone failed") else 2
        console.print(f"[red]Source error:[/red] {exc}")
        raise typer.Exit(code=code) from None


def _print_run_result_paths(result: Any) -> None:
    _print_summary(
        result.report.confidence,
        result.files_scanned,
        result.report,
        dry_run=result.dry_run,
    )
    if result.markdown_path:
        console.print(f"[green]Markdown report:[/green] {result.markdown_path}")
    if result.json_path:
        console.print(f"[green]JSON report:[/green] {result.json_path}")
    if result.sarif_path:
        console.print(f"[green]SARIF report:[/green] {result.sarif_path}")
    if result.aborted:
        raise typer.Exit(code=130)


def _apply_fail_on_and_ratchet(
    *,
    result: Any,
    fail_on: str | None,
    mode: str,
    ratchet: bool,
    resolved_root: Path,
) -> None:
    try:
        scanner_only = bool(
            result.report.provenance is not None and result.report.provenance.failOnScannerOnly
        )
        triggered = fail_on_triggered(result.report, fail_on, scanner_only=scanner_only)
    except ValueError as exc:
        console.print(f"[red]Usage error:[/red] {exc}")
        raise typer.Exit(code=EXIT_BAD_INPUT) from exc

    # Ratchet is review-only (not sentinel/architecture). Runs while the source
    # tree still exists (before ephemeral cleanup). Either --fail-on or ratchet
    # breach may yield exit 1.
    ratchet_breached = False
    if not result.dry_run and mode == "review":
        ratchet_breached = _ratchet_breached_for_review(resolved_root, ratchet_flag=ratchet)
    if triggered or ratchet_breached:
        raise typer.Exit(code=1)


def _call_run_review(request: RunRequest, resolved_root: Path, out_dir: Path | None) -> Any:
    return run_review(ReviewRun(
        path=resolved_root,
        mode=request.mode,
        review_mode=request.review_mode,
        since=request.since,
        out_dir=out_dir,
        fmt=request.fmt,
        model_override=request.model,
        timeout_override=request.timeout,
        force_full=request.force_full,
        force_changed=request.force_changed,
        git_diff=request.git_diff,
        deep_passes=request.deep_passes,
        full_audit=request.full_audit,
        dry_run=request.dry_run,
        trust_project=request.trust_project,
        scanners=request.scanners,
        require_scanners=request.require_scanners,
        scanners_only=request.scanners_only,
        progress=request.progress,
        deep=request.deep,
        ci=request.ci,
        sarif=request.sarif,
        verify_findings=request.verify_findings,
        packs=request.packs,
        fallback=request.fallback,
        import_sarif=request.import_sarif or [],
        require_sarif_import=request.require_sarif_import,
        model_lock=request.model_lock,
        resume=request.resume,
        role_packs=request.role_packs,
        retry_passes=request.retry_passes,
        invoked_command=request.invoked_command,
        expanded_argv=request.expanded_argv,
    ))


def _execute_run_mode(request: RunRequest) -> Any:
    """Run review after source resolve."""
    resolved = _resolve_run_source(
        path=request.path,
        git_url=request.git_url,
        github=request.github,
        bitbucket=request.bitbucket,
        hf=request.hf,
        ref=request.ref,
    )
    out_dir = request.out
    if out_dir is None and resolved.ephemeral:
        out_dir = Path.cwd() / "reports"
    if not request.quiet:
        console.print(f"[dim]Source:[/dim] {resolved.label}")
    result = _call_run_review(request, resolved.root, out_dir)
    _print_run_result_paths(result)
    if request.explain_uuids and not result.dry_run:
        from repolens.cli.commands_explain import run_post_review_explains

        run_post_review_explains(request.explain_uuids, path=request.path, result=result)
    _apply_fail_on_and_ratchet(
        result=result,
        fail_on=request.fail_on,
        mode=request.mode,
        ratchet=request.ratchet,
        resolved_root=resolved.root,
    )
    return resolved
