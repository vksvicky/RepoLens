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
    expanded_argv = build_expanded_argv(
        _resolved_invocation(
            mode=mode, path=path, git_url=git_url, github=github, bitbucket=bitbucket,
            hf=hf, ref=ref, review_mode=review_mode, since=since, out=out, fmt=fmt,
            model=model, fail_on=fail_on, dry_run=dry_run, full_audit=full_audit,
            trust_project=trust_project, scanners=scanners,
            require_scanners=require_scanners, scanners_only=scanners_only,
            timeout=timeout, force_full=force_full, force_changed=force_changed,
            git_diff=git_diff, deep_passes=deep_passes, deep=deep, ci=ci, sarif=sarif,
            verify_findings=verify_findings, packs=packs, fallback=fallback,
            ratchet=ratchet, import_sarif=import_sarif,
            require_sarif_import=require_sarif_import, model_lock=model_lock,
            role_packs=role_packs, retry_passes=retry_passes,
        )
    )
    invoked_command = command_for_provenance(expanded_argv)
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
            retry_passes=retry_passes, invoked_command=invoked_command,
            expanded_argv=expanded_argv,
        )
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


def _resolved_invocation(**kw: Any) -> ResolvedInvocation:
    """Build argv inputs from the operator's flags, not the resolved checkout."""
    return ResolvedInvocation(
        mode=str(kw["mode"]),
        path=_as_str(kw["path"]),
        git_url=kw["git_url"],
        github=kw["github"],
        bitbucket=kw["bitbucket"],
        hf=kw["hf"],
        ref=kw["ref"],
        force_full=bool(kw["force_full"]),
        force_changed=bool(kw["force_changed"]),
        full_audit=bool(kw["full_audit"]),
        scanners_only=bool(kw["scanners_only"]),
        deep=kw["deep"],
        timeout=kw["timeout"],
        git_diff=kw["git_diff"],
        scanners=kw["scanners"],
        fail_on=kw["fail_on"],
        ratchet=bool(kw["ratchet"]),
        verify_findings=kw["verify_findings"],
        out=_as_str(kw["out"]),
        fmt=kw["fmt"],
        ci=bool(kw["ci"]),
        model=kw["model"],
        deep_passes=kw["deep_passes"],
        sarif=bool(kw["sarif"]),
        role_packs=kw["role_packs"],
        import_sarif=tuple(_as_str(path) or "" for path in (kw["import_sarif"] or [])),
        require_scanners=bool(kw["require_scanners"]),
        since=kw["since"],
        retry_passes=tuple(kw["retry_passes"] or ()),
        packs=tuple(kw["packs"] or ()),
        trust_project=bool(kw["trust_project"]),
        dry_run=bool(kw["dry_run"]),
        review_mode=kw["review_mode"],
        require_sarif_import=bool(kw["require_sarif_import"]),
        fallback=kw["fallback"],
        model_lock=kw["model_lock"],
    )


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
    _body_review(
        path, git_url, github, bitbucket, hf, ref, mode, since, out, fmt, model,
        fail_on, dry_run, full_audit, trust_project, scanners, require_scanners,
        scanners_only, quiet, verbose, heartbeat, timeout, model_lock_flag,
        no_model_lock, force_full, force_changed, git_diff, deep, deep_passes,
        explain, ci, sarif, verify, pack, fallback, ratchet,
        import_sarif, require_sarif_import, resume, role_packs, retry_passes,
    )
