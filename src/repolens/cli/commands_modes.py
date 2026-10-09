"""``repolens sentinel`` and ``repolens architecture`` commands."""

from __future__ import annotations

from pathlib import Path

from repolens.cli.app import app
from repolens.cli.commands_review import _run_mode
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
from repolens.cli.review_options import (
    option_ci,
    option_deep,
    option_deep_passes,
    option_dry_run,
    option_fail_on_short,
    option_fallback,
    option_format,
    option_import_sarif,
    option_model,
    option_out,
    option_pack,
    option_require_sarif_import,
    option_review_mode,
    option_sarif,
    option_since,
    option_verify_findings,
)


@app.command()
def sentinel(
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
    fail_on: str | None = option_fail_on_short(),
    dry_run: bool = option_dry_run(),
    trust_project: bool = option_trust_project(),
    scanners: str = option_scanners(),
    require_scanners: bool = option_require_scanners(),
    scanners_only: bool = option_scanners_only(),
    quiet: bool = option_quiet(),
    verbose: bool = option_verbose(),
    heartbeat: float = option_heartbeat(),
    timeout: float | None = option_timeout(),
    force_full: bool = option_force_full(),
    force_changed: bool = option_force_changed(),
    git_diff: str | None = option_git_diff(),
    deep: bool | None = option_deep(),
    deep_passes: int | None = option_deep_passes(),
    ci: bool = option_ci(),
    sarif: bool = option_sarif(),
    verify_findings: bool | None = option_verify_findings(),
    pack: list[str] | None = option_pack(),
    fallback: bool = option_fallback(),
    import_sarif: list[Path] | None = option_import_sarif(),
    require_sarif_import: bool = option_require_sarif_import(),
) -> None:
    """Security-only review (P1 playbook)."""
    _body_sentinel(
        path, git_url, github, bitbucket, hf, ref, mode, since, out, fmt, model,
        fail_on, dry_run, trust_project, scanners, require_scanners, scanners_only,
        quiet, verbose, heartbeat, timeout, force_full, force_changed, git_diff,
        deep, deep_passes, ci, sarif, verify_findings, pack, fallback,
        import_sarif, require_sarif_import,
    )


def _body_sentinel(
    path, git_url, github, bitbucket, hf, ref, mode, since, out, fmt, model,
    fail_on, dry_run, trust_project, scanners, require_scanners, scanners_only,
    quiet, verbose, heartbeat, timeout, force_full, force_changed, git_diff,
    deep, deep_passes, ci, sarif, verify_findings, pack, fallback,
    import_sarif, require_sarif_import,
) -> None:
    _run_mode(
        "sentinel", path, git_url, github, bitbucket, hf, ref, mode, since, out, fmt,
        model, fail_on, dry_run, False, trust_project, scanners, require_scanners,
        scanners_only, quiet, verbose, heartbeat, timeout, force_full, force_changed,
        git_diff, deep_passes, deep, None, ci, sarif, verify_findings, pack, fallback,
        False, import_sarif, require_sarif_import,
    )


@app.command()
def architecture(
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
    fail_on: str | None = option_fail_on_short(),
    dry_run: bool = option_dry_run(),
    trust_project: bool = option_trust_project(),
    scanners: str = option_scanners(),
    require_scanners: bool = option_require_scanners(),
    scanners_only: bool = option_scanners_only(),
    quiet: bool = option_quiet(),
    verbose: bool = option_verbose(),
    heartbeat: float = option_heartbeat(),
    timeout: float | None = option_timeout(),
    force_full: bool = option_force_full(),
    force_changed: bool = option_force_changed(),
    git_diff: str | None = option_git_diff(),
    deep: bool | None = option_deep(),
    deep_passes: int | None = option_deep_passes(),
    ci: bool = option_ci(),
    sarif: bool = option_sarif(),
    verify_findings: bool | None = option_verify_findings(),
    pack: list[str] | None = option_pack(),
    fallback: bool = option_fallback(),
    import_sarif: list[Path] | None = option_import_sarif(),
    require_sarif_import: bool = option_require_sarif_import(),
) -> None:
    """Architecture / production-readiness audit."""
    _body_architecture(
        path, git_url, github, bitbucket, hf, ref, mode, since, out, fmt, model,
        fail_on, dry_run, trust_project, scanners, require_scanners, scanners_only,
        quiet, verbose, heartbeat, timeout, force_full, force_changed, git_diff,
        deep, deep_passes, ci, sarif, verify_findings, pack, fallback,
        import_sarif, require_sarif_import,
    )


def _body_architecture(
    path, git_url, github, bitbucket, hf, ref, mode, since, out, fmt, model,
    fail_on, dry_run, trust_project, scanners, require_scanners, scanners_only,
    quiet, verbose, heartbeat, timeout, force_full, force_changed, git_diff,
    deep, deep_passes, ci, sarif, verify_findings, pack, fallback,
    import_sarif, require_sarif_import,
) -> None:
    _run_mode(
        "architecture", path, git_url, github, bitbucket, hf, ref, mode, since, out,
        fmt, model, fail_on, dry_run, True, trust_project, scanners, require_scanners,
        scanners_only, quiet, verbose, heartbeat, timeout, force_full, force_changed,
        git_diff, deep_passes, deep, None, ci, sarif, verify_findings, pack, fallback,
        False, import_sarif, require_sarif_import,
    )
