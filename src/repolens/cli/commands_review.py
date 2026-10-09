"""Review / sentinel / architecture CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from repolens.cli.app import app, console
from repolens.cli.commands_review_support import (
    _execute_run_mode,
    _map_run_mode_error,
    _reject_run_flags,
)
from repolens.cli.pack_scope import (
    option_bitbucket,
    option_force_changed,
    option_force_full,
    option_git_diff,
    option_git_url,
    option_github,
    option_heartbeat,
    option_hf,
    option_path,
    option_quiet,
    option_ref,
    option_require_scanners,
    option_scanners,
    option_scanners_only,
    option_timeout,
    option_trust_project,
    option_verbose,
)
from repolens.cli.presets import ReviewFlagBag, apply_preset, parse_preset
from repolens.cli.review_options import (
    normalize_retry_passes,
    option_ci,
    option_deep,
    option_deep_passes,
    option_dry_run,
    option_explain,
    option_fail_on,
    option_fallback,
    option_format,
    option_full_audit,
    option_import_sarif,
    option_model,
    option_model_lock,
    option_no_model_lock,
    option_out,
    option_pack,
    option_preset,
    option_ratchet,
    option_require_sarif_import,
    option_resume,
    option_retry_pass,
    option_review_mode,
    option_role_packs,
    option_sarif,
    option_since,
    option_verify_findings,
)
from repolens.progress import ReviewProgress
from repolens.sources import cleanup_source


def _run_mode(
    mode: str,
    path: str | Path | None,
    git_url: str | None,
    github: str | None,
    bitbucket: str | None,
    hf: str | None,
    ref: str | None,
    review_mode: str,
    since: str | None,
    out: Path | None,
    fmt: str,
    model: str | None,
    fail_on: str | None,
    dry_run: bool,
    full_audit: bool,
    trust_project: bool,
    scanners: str,
    require_scanners: bool,
    scanners_only: bool,
    quiet: bool = False,
    verbose: bool = False,
    heartbeat: float = 15.0,
    timeout: float | None = None,
    force_full: bool = False,
    force_changed: bool = False,
    git_diff: str | None = None,
    deep_passes: int | None = None,
    deep: bool | None = None,
    explain_uuids: str | None = None,
    ci: bool = False,
    sarif: bool = False,
    verify_findings: bool | None = None,
    packs: list[str] | None = None,
    fallback: bool = True,
    ratchet: bool = False,
    import_sarif: list[Path] | None = None,
    require_sarif_import: bool = False,
    no_model_lock: bool = False,
    model_lock: bool | None = None,
    resume: bool = True,
    role_packs: bool | None = None,
    retry_passes: list[str] | None = None,
) -> None:
    _reject_run_flags(
        fmt=fmt, require_sarif_import=require_sarif_import, import_sarif=import_sarif,
        scanners_only=scanners_only, dry_run=dry_run, force_full=force_full,
        force_changed=force_changed, git_diff=git_diff, deep_passes=deep_passes,
        quiet=quiet, verbose=verbose, model_lock=model_lock, no_model_lock=no_model_lock,
    )
    progress = ReviewProgress(
        quiet=quiet, verbose=verbose, heartbeat_seconds=heartbeat, console=console,
    )
    resolved = None
    try:
        resolved = _execute_run_mode(
            mode=mode, path=path, git_url=git_url, github=github, bitbucket=bitbucket,
            hf=hf, ref=ref, review_mode=review_mode, since=since, out=out, fmt=fmt,
            model=model, fail_on=fail_on, dry_run=dry_run, full_audit=full_audit,
            trust_project=trust_project, scanners=scanners,
            require_scanners=require_scanners, scanners_only=scanners_only,
            quiet=quiet, timeout=timeout, force_full=force_full,
            force_changed=force_changed, git_diff=git_diff, deep_passes=deep_passes,
            deep=deep, explain_uuids=explain_uuids, ci=ci, sarif=sarif,
            verify_findings=verify_findings, packs=packs, fallback=fallback,
            ratchet=ratchet, import_sarif=import_sarif,
            require_sarif_import=require_sarif_import, model_lock=model_lock,
            resume=resume, role_packs=role_packs, progress=progress,
            retry_passes=retry_passes,
        )
    except typer.Exit:
        raise
    except Exception as exc:
        _map_run_mode_error(exc)
        raise
    finally:
        if resolved is not None:
            cleanup_source(resolved)


def _normalize_retry_passes_or_exit(raw: list[str] | None) -> list[str] | None:
    """Validate ``--retry-pass`` values at the CLI boundary (exit 2 on bad input)."""
    if not raw:
        return None
    try:
        return sorted(normalize_retry_passes(raw))
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc


def _resolve_preset(preset: str | None, **flags: Any) -> tuple[Any, ...]:
    """Apply ``--preset`` to the flag values; explicit CLI flags win."""
    keys = ("scanners_only", "ci", "deep", "git_diff", "force_full",
            "force_changed", "full_audit", "timeout")
    try:
        name = parse_preset(preset)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    if name is None:
        return tuple(flags[k] for k in keys)
    bag = apply_preset(name, ReviewFlagBag(**flags))
    return tuple(getattr(bag, k) for k in keys)


@app.command()
def review(
    path: str | None = option_path(),
    git_url: str | None = option_git_url(),
    github: str | None = option_github(),
    bitbucket: str | None = option_bitbucket(),
    hf: str | None = option_hf(),
    ref: str | None = option_ref(),
    mode: str = option_review_mode(),
    since: str | None = option_since(),
    out: Path | None = option_out(),
    fmt: str = option_format(),
    model: str | None = option_model(),
    fail_on: str | None = option_fail_on(),
    dry_run: bool = option_dry_run(),
    full_audit: bool = option_full_audit(),
    trust_project: bool = option_trust_project(),
    scanners: str = option_scanners(),
    require_scanners: bool = option_require_scanners(),
    scanners_only: bool = option_scanners_only(),
    quiet: bool = option_quiet(),
    verbose: bool = option_verbose(),
    heartbeat: float = option_heartbeat(),
    timeout: float | None = option_timeout(),
    model_lock_flag: bool = option_model_lock(),
    no_model_lock: bool = option_no_model_lock(),
    force_full: bool = option_force_full(),
    force_changed: bool = option_force_changed(),
    git_diff: str | None = option_git_diff(),
    deep: bool | None = option_deep(),
    deep_passes: int | None = option_deep_passes(),
    explain: str | None = option_explain(),
    ci: bool = option_ci(),
    sarif: bool = option_sarif(),
    verify_findings: bool | None = option_verify_findings(),
    pack: list[str] | None = option_pack(),
    fallback: bool = option_fallback(),
    ratchet: bool = option_ratchet(),
    import_sarif: list[Path] | None = option_import_sarif(),
    require_sarif_import: bool = option_require_sarif_import(),
    resume: bool = option_resume(),
    role_packs: bool | None = option_role_packs(),
    preset: str | None = option_preset(),
    retry_pass: list[str] | None = option_retry_pass(),
) -> None:
    """Full P1→P2→P3 dual review. ``--preset`` bundles flags; explicit flags win."""
    retry_passes = _normalize_retry_passes_or_exit(retry_pass)
    (scanners_only, ci, deep, git_diff, force_full, force_changed, full_audit,
     timeout) = _resolve_preset(
        preset, scanners_only=scanners_only, ci=ci, dry_run=dry_run, deep=deep,
        git_diff=git_diff, force_full=force_full, force_changed=force_changed,
        full_audit=full_audit, timeout=timeout,
    )
    _body_review(
        path, git_url, github, bitbucket, hf, ref, mode, since, out, fmt, model,
        fail_on, dry_run, full_audit, trust_project, scanners, require_scanners,
        scanners_only, quiet, verbose, heartbeat, timeout, model_lock_flag,
        no_model_lock, force_full, force_changed, git_diff, deep, deep_passes,
        explain, ci, sarif, verify_findings, pack, fallback, ratchet,
        import_sarif, require_sarif_import, resume, role_packs, retry_passes,
    )


def _body_review(  # type: ignore[no-untyped-def]
    path, git_url, github, bitbucket, hf, ref, mode, since, out, fmt, model,
    fail_on, dry_run, full_audit, trust_project, scanners, require_scanners,
    scanners_only, quiet, verbose, heartbeat, timeout, model_lock_flag,
    no_model_lock, force_full, force_changed, git_diff, deep, deep_passes,
    explain, ci, sarif, verify_findings, pack, fallback, ratchet,
    import_sarif, require_sarif_import, resume, role_packs, retry_passes=None,
) -> None:
    lock = True if model_lock_flag else False if no_model_lock else None
    _run_mode(
        "review", path, git_url, github, bitbucket, hf, ref, mode, since, out, fmt,
        model, fail_on, dry_run, full_audit, trust_project, scanners,
        require_scanners, scanners_only, quiet, verbose, heartbeat, timeout,
        force_full, force_changed, git_diff, deep_passes, deep, explain, ci, sarif,
        verify_findings, pack, fallback, ratchet, import_sarif,
        require_sarif_import, no_model_lock, lock, resume, role_packs,
        retry_passes=retry_passes,
    )
