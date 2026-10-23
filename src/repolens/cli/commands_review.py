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
from repolens.cli.exit_codes import EXIT_BAD_INPUT
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
from repolens.cli.resolved_argv import (
    ResolvedInvocation,
    build_expanded_argv,
    command_for_provenance,
)
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
    option_ratchet_default_on,
    option_require_sarif_import,
    option_resume,
    option_retry_pass,
    option_review_mode,
    option_role_packs,
    option_sarif,
    option_since,
    option_verify_findings,
)
from repolens.cli.run_request import RunRequest
from repolens.progress import ReviewProgress
from repolens.sources import cleanup_source


def _start(command: str, **fields: Any) -> None:
    """Build one run request from CLI flag names and execute it."""
    review_mode = str(fields.pop("mode", "full"))
    packs = fields.pop("pack", None)
    explain = fields.pop("explain", None)
    lock_flag = bool(fields.pop("model_lock_flag", False))
    no_lock = bool(fields.pop("no_model_lock", False))
    if command == "architecture":
        fields.setdefault("full_audit", True)
    _run_mode(
        RunRequest(
            mode=command,
            review_mode=review_mode,
            packs=packs,
            explain_uuids=explain,
            no_model_lock=no_lock,
            model_lock=True if lock_flag else False if no_lock else None,
            **fields,
        )
    )


def _run_mode(request: RunRequest) -> None:
    _reject_run_flags(request)
    request.progress = ReviewProgress(
        quiet=request.quiet,
        verbose=request.verbose,
        heartbeat_seconds=request.heartbeat,
        console=console,
    )
    request.expanded_argv = build_expanded_argv(_resolved_invocation(request))
    request.invoked_command = command_for_provenance(request.expanded_argv)
    resolved = None
    try:
        resolved = _execute_run_mode(request)
    except typer.Exit:
        raise
    except Exception as exc:
        _map_run_mode_error(exc)
        raise
    finally:
        if resolved is not None:
            cleanup_source(resolved)


def _as_str(value: str | Path | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _resolved_invocation(request: RunRequest) -> ResolvedInvocation:
    """Build argv inputs from the operator's flags, not the resolved checkout."""
    return ResolvedInvocation(
        mode=str(request.mode),
        path=_as_str(request.path),
        git_url=request.git_url,
        github=request.github,
        bitbucket=request.bitbucket,
        hf=request.hf,
        ref=request.ref,
        force_full=bool(request.force_full),
        force_changed=bool(request.force_changed),
        full_audit=bool(request.full_audit),
        scanners_only=bool(request.scanners_only),
        deep=request.deep,
        timeout=request.timeout,
        git_diff=request.git_diff,
        scanners=request.scanners,
        fail_on=request.fail_on,
        ratchet=bool(request.ratchet),
        verify_findings=request.verify_findings,
        out=_as_str(request.out),
        fmt=request.fmt,
        ci=bool(request.ci),
        model=request.model,
        deep_passes=request.deep_passes,
        sarif=bool(request.sarif),
        role_packs=request.role_packs,
        import_sarif=tuple(_as_str(path) or "" for path in (request.import_sarif or [])),
        require_scanners=bool(request.require_scanners),
        since=request.since,
        retry_passes=tuple(request.retry_passes or ()),
        packs=tuple(request.packs or ()),
        trust_project=bool(request.trust_project),
        dry_run=bool(request.dry_run),
        review_mode=request.review_mode,
        require_sarif_import=bool(request.require_sarif_import),
        fallback=request.fallback,
        model_lock=request.model_lock,
    )


def _normalize_retry_passes_or_exit(raw: list[str] | None) -> list[str] | None:
    """Validate ``--retry-pass`` values at the CLI boundary (exit 2 on bad input)."""
    if not raw:
        return None
    try:
        return sorted(normalize_retry_passes(raw))
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=EXIT_BAD_INPUT) from exc


def _resolve_preset(preset: str | None, **flags: Any) -> tuple[Any, ...]:
    """Apply ``--preset`` to the flag values; explicit CLI flags win."""
    keys = ("scanners_only", "ci", "deep", "git_diff", "force_full",
            "force_changed", "full_audit", "timeout")
    try:
        name = parse_preset(preset)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=EXIT_BAD_INPUT) from exc
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
    _start(
        "review", path=path, git_url=git_url, github=github, bitbucket=bitbucket,
        hf=hf, ref=ref, mode=mode, since=since, out=out, fmt=fmt, model=model,
        fail_on=fail_on, dry_run=dry_run, full_audit=full_audit,
        trust_project=trust_project, scanners=scanners,
        require_scanners=require_scanners, scanners_only=scanners_only, quiet=quiet,
        verbose=verbose, heartbeat=heartbeat, timeout=timeout,
        model_lock_flag=model_lock_flag, no_model_lock=no_model_lock,
        force_full=force_full, force_changed=force_changed, git_diff=git_diff,
        deep=deep, deep_passes=deep_passes, explain=explain, ci=ci, sarif=sarif,
        verify_findings=verify_findings, pack=pack, fallback=fallback, ratchet=ratchet,
        import_sarif=import_sarif, require_sarif_import=require_sarif_import,
        resume=resume, role_packs=role_packs, retry_passes=retry_passes,
    )


@app.command("audit")
def audit(
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
    ratchet: bool = option_ratchet_default_on(),
    import_sarif: list[Path] | None = option_import_sarif(),
    require_sarif_import: bool = option_require_sarif_import(),
    resume: bool = option_resume(),
    role_packs: bool | None = option_role_packs(),
    retry_pass: list[str] | None = option_retry_pass(),
) -> None:
    """One-command due-diligence kit (= ``review --preset release`` + ratchet + verify)."""
    retry_passes = _normalize_retry_passes_or_exit(retry_pass)
    (scanners_only, ci, deep, git_diff, force_full, force_changed, full_audit,
     timeout) = _resolve_preset(
        "release", scanners_only=scanners_only, ci=ci, dry_run=dry_run, deep=deep,
        git_diff=git_diff, force_full=force_full, force_changed=force_changed,
        full_audit=full_audit, timeout=timeout,
    )
    verify = True if verify_findings is None else verify_findings
    _start(
        "review", path=path, git_url=git_url, github=github, bitbucket=bitbucket,
        hf=hf, ref=ref, mode=mode, since=since, out=out, fmt=fmt, model=model,
        fail_on=fail_on, dry_run=dry_run, full_audit=full_audit,
        trust_project=trust_project, scanners=scanners,
        require_scanners=require_scanners, scanners_only=scanners_only, quiet=quiet,
        verbose=verbose, heartbeat=heartbeat, timeout=timeout,
        model_lock_flag=model_lock_flag, no_model_lock=no_model_lock,
        force_full=force_full, force_changed=force_changed, git_diff=git_diff,
        deep=deep, deep_passes=deep_passes, explain=explain, ci=ci, sarif=sarif,
        verify_findings=verify, pack=pack, fallback=fallback, ratchet=ratchet,
        import_sarif=import_sarif, require_sarif_import=require_sarif_import,
        resume=resume, role_packs=role_packs, retry_passes=retry_passes,
    )
