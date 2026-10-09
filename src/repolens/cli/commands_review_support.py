"""Ratchet, flag checks, and run-mode helpers for ``repolens review``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from repolens.cli.app import _coerce_local_path, console
from repolens.cli.commands_check import _print_fingerprint_delta, _resolve_baseline_path
from repolens.cli.export import _print_summary
from repolens.config import load_config
from repolens.graph import analyse_repo_graph
from repolens.graph.baseline import load_baseline
from repolens.graph.ratchet import evaluate_ratchet
from repolens.graph.types import GraphStatus
from repolens.llm import LlmError
from repolens.pipeline import ScannerRequirementError, fail_on_triggered, run_review
from repolens.progress import ReviewProgress
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


def _reject_run_flags(
    *,
    fmt: str,
    require_sarif_import: bool,
    import_sarif: list[Path] | None,
    scanners_only: bool,
    dry_run: bool,
    force_full: bool,
    force_changed: bool,
    git_diff: str | None,
    deep_passes: int | None,
    quiet: bool,
    verbose: bool,
    model_lock: bool | None,
    no_model_lock: bool,
) -> None:
    if fmt not in {"md", "json", "both"}:
        console.print("[red]--format must be md | json | both[/red]")
        raise typer.Exit(code=2)
    if require_sarif_import and not import_sarif:
        console.print(
            "[red]--require-sarif-import needs at least one --import-sarif path[/red]"
        )
        raise typer.Exit(code=2)
    if scanners_only and dry_run:
        console.print("[red]--scanners-only cannot be combined with --dry-run[/red]")
        raise typer.Exit(code=2)
    if force_full and force_changed:
        console.print("[red]--full and --changed cannot be combined[/red]")
        raise typer.Exit(code=2)
    if git_diff is not None and force_full:
        console.print("[red]--full and --git-diff cannot be combined[/red]")
        raise typer.Exit(code=2)
    if git_diff is not None and force_changed:
        console.print("[red]--changed and --git-diff cannot be combined[/red]")
        raise typer.Exit(code=2)
    if deep_passes is not None and deep_passes < 1:
        console.print("[red]--deep-passes must be >= 1[/red]")
        raise typer.Exit(code=2)
    if quiet and verbose:
        console.print("[red]--quiet and --verbose cannot be combined[/red]")
        raise typer.Exit(code=2)
    if model_lock is True and no_model_lock:
        console.print("[red]--model-lock and --no-model-lock cannot be combined[/red]")
        raise typer.Exit(code=2)


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
            result.report.provenance is not None
            and result.report.provenance.failOnScannerOnly
        )
        triggered = fail_on_triggered(
            result.report, fail_on, scanner_only=scanner_only
        )
    except ValueError as exc:
        console.print(f"[red]Usage error:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    # Ratchet is review-only (not sentinel/architecture). Runs while the source
    # tree still exists (before ephemeral cleanup). Either --fail-on or ratchet
    # breach may yield exit 1.
    ratchet_breached = False
    if not result.dry_run and mode == "review":
        ratchet_breached = _ratchet_breached_for_review(
            resolved_root, ratchet_flag=ratchet
        )
    if triggered or ratchet_breached:
        raise typer.Exit(code=1)


def _call_run_review(
    *,
    resolved_root: Path,
    mode: str,
    review_mode: str,
    since: str | None,
    out_dir: Path | None,
    fmt: str,
    model: str | None,
    timeout: float | None,
    force_full: bool,
    force_changed: bool,
    git_diff: str | None,
    deep_passes: int | None,
    full_audit: bool,
    dry_run: bool,
    trust_project: bool,
    scanners: str,
    require_scanners: bool,
    scanners_only: bool,
    progress: ReviewProgress,
    deep: bool | None,
    ci: bool,
    sarif: bool,
    verify_findings: bool | None,
    packs: list[str] | None,
    fallback: bool,
    import_sarif: list[Path] | None,
    require_sarif_import: bool,
    model_lock: bool | None,
    resume: bool,
    role_packs: bool | None,
    retry_passes: list[str] | None = None,
) -> Any:
    return run_review(
        path=resolved_root, mode=mode, review_mode=review_mode, since=since,
        out_dir=out_dir, fmt=fmt, model_override=model, timeout_override=timeout,
        force_full=force_full, force_changed=force_changed, git_diff=git_diff,
        deep_passes=deep_passes, full_audit=full_audit, dry_run=dry_run,
        trust_project=trust_project, scanners=scanners,
        require_scanners=require_scanners, scanners_only=scanners_only,
        progress=progress, deep=deep, ci=ci, sarif=sarif,
        verify_findings=verify_findings, packs=packs, fallback=fallback,
        import_sarif=import_sarif or [], require_sarif_import=require_sarif_import,
        model_lock=model_lock, resume=resume, role_packs=role_packs,
        retry_passes=retry_passes,
    )


def _execute_run_mode(**kw: Any) -> Any:
    """Run review after source resolve. Keyword args match ``_run_mode`` fields."""
    resolved = _resolve_run_source(
        path=kw["path"], git_url=kw["git_url"], github=kw["github"],
        bitbucket=kw["bitbucket"], hf=kw["hf"], ref=kw["ref"],
    )
    out_dir = kw["out"]
    if out_dir is None and resolved.ephemeral:
        out_dir = Path.cwd() / "reports"
    if not kw["quiet"]:
        console.print(f"[dim]Source:[/dim] {resolved.label}")
    result = _call_run_review(
        resolved_root=resolved.root, mode=kw["mode"], review_mode=kw["review_mode"],
        since=kw["since"], out_dir=out_dir, fmt=kw["fmt"], model=kw["model"],
        timeout=kw["timeout"], force_full=kw["force_full"],
        force_changed=kw["force_changed"], git_diff=kw["git_diff"],
        deep_passes=kw["deep_passes"], full_audit=kw["full_audit"],
        dry_run=kw["dry_run"], trust_project=kw["trust_project"],
        scanners=kw["scanners"], require_scanners=kw["require_scanners"],
        scanners_only=kw["scanners_only"], progress=kw["progress"], deep=kw["deep"],
        ci=kw["ci"], sarif=kw["sarif"], verify_findings=kw["verify_findings"],
        packs=kw["packs"], fallback=kw["fallback"], import_sarif=kw["import_sarif"],
        require_sarif_import=kw["require_sarif_import"], model_lock=kw["model_lock"],
        resume=kw["resume"], role_packs=kw["role_packs"],
        retry_passes=kw.get("retry_passes"),
    )
    _print_run_result_paths(result)
    if kw["explain_uuids"] and not result.dry_run:
        from repolens.cli.commands_explain import run_post_review_explains

        run_post_review_explains(kw["explain_uuids"], path=kw["path"], result=result)
    _apply_fail_on_and_ratchet(
        result=result, fail_on=kw["fail_on"], mode=kw["mode"],
        ratchet=kw["ratchet"], resolved_root=resolved.root,
    )
    return resolved
