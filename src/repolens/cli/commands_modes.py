"""``repolens sentinel`` and ``repolens architecture`` commands."""

from __future__ import annotations

from pathlib import Path

import typer

from repolens.cli.app import app
from repolens.cli.commands_review import _run_mode
from repolens.cli.pack_scope import (
    option_force_changed,
    option_force_full,
    option_git_diff,
)

@app.command()
def sentinel(
    path: str | None = typer.Option(
        None, "--path", help="Local project root (default: .)"
    ),
    git_url: str | None = typer.Option(None, "--git-url", help="Git clone URL"),
    github: str | None = typer.Option(None, "--github", help="GitHub OWNER/REPO"),
    bitbucket: str | None = typer.Option(
        None, "--bitbucket", help="Bitbucket WORKSPACE/REPO"
    ),
    hf: str | None = typer.Option(
        None, "--hf", help="Hugging Face Hub id (ORG/NAME or datasets|spaces/ORG/NAME)"
    ),
    ref: str | None = typer.Option(None, "--ref", help="Branch/tag for remotes"),
    mode: str = typer.Option("full", "--mode", help="full | diff"),
    since: str | None = typer.Option(None, "--since", help="Diff base ref"),
    out: Path | None = typer.Option(None, "--out", help="Report directory"),
    fmt: str = typer.Option("md", "--format", help="md | json | both"),
    model: str | None = typer.Option(None, "--model", help="Override model name"),
    fail_on: str | None = typer.Option(None, "--fail-on", help="Exit 1 severity threshold"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inventory only; no LLM call"),
    trust_project: bool = typer.Option(
        False,
        "--trust-project-config",
        help="Allow project .repolens.toml to set provider/base_url/api_key_env",
    ),
    scanners: str = typer.Option(
        "auto",
        "--scanners",
        help="auto | off | comma list (gitleaks,semgrep,osv,trivy,checkov)",
    ),
    require_scanners: bool = typer.Option(
        False, "--require-scanners", help="Exit 2 if a requested scanner is missing"
    ),
    scanners_only: bool = typer.Option(
        False, "--scanners-only", help="Skip LLM; report scanner findings only"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Hide progress status lines"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Extra progress detail (file sample, scanner status)"
    ),
    heartbeat: float = typer.Option(
        15.0,
        "--heartbeat",
        help="Seconds between LLM wait heartbeats (0 disables)",
    ),
    timeout: float | None = typer.Option(
        None,
        "--timeout",
        help="LLM HTTP timeout in seconds (default: 900 for ollama, 120 otherwise)",
    ),
    force_full: bool = option_force_full(),
    force_changed: bool = option_force_changed(),
    git_diff: str | None = option_git_diff(),
    deep: bool | None = typer.Option(
        None,
        "--deep/--no-deep",
        help="Multi-pass deep coverage (default: on; --no-deep = single-shot)",
    ),
    deep_passes: int | None = typer.Option(
        None,
        "--deep-passes",
        help="Cap deep band passes (1 = P1-only). Overrides [deep].max_passes.",
        min=1,
    ),
    ci: bool = typer.Option(
        False,
        "--ci",
        help="PR/CI recipe: triage routing, --changed pack, single-shot LLM on scanner hits only",
    ),
    sarif: bool = typer.Option(
        False,
        "--sarif",
        help="Write anchored SARIF 2.1 (scanner locations + resolvable anchors only)",
    ),
    verify_findings: bool | None = typer.Option(
        None,
        "--verify-findings/--no-verify-findings",
        help="Re-check Critical locations (non-fatal; default: [deep].verify_findings)",
    ),
    pack: list[str] | None = typer.Option(
        None,
        "--pack",
        help="Enable a domain pack (repeatable); see `repolens packs list`",
    ),
    fallback: bool = typer.Option(
        True,
        "--fallback/--no-fallback",
        help=(
            "Automatically fall back to local Ollama or SAST scanners "
            "when Cloud AI is unavailable"
        ),
    ),
    import_sarif: list[Path] | None = typer.Option(
        None,
        "--import-sarif",
        help="Merge findings from a SARIF 2.1 file (repeatable). Treated as scanner evidence.",
    ),
    require_sarif_import: bool = typer.Option(
        False,
        "--require-sarif-import",
        help=(
            "Exit 2 if any --import-sarif path is missing or unreadable "
            "(default: soft-fail and continue)"
        ),
    ),
) -> None:
    """Security-only review (P1 playbook)."""
    _run_mode(
        "sentinel",
        path,
        git_url,
        github,
        bitbucket,
        hf,
        ref,
        mode,
        since,
        out,
        fmt,
        model,
        fail_on,
        dry_run,
        False,
        trust_project,
        scanners,
        require_scanners,
        scanners_only,
        quiet,
        verbose,
        heartbeat,
        timeout,
        force_full,
        force_changed,
        git_diff,
        deep_passes,
        deep,
        None,
        ci,
        sarif,
        verify_findings,
        pack,
        fallback,
        False,
        import_sarif,
        require_sarif_import,
    )


@app.command()
def architecture(
    path: str | None = typer.Option(
        None, "--path", help="Local project root (default: .)"
    ),
    git_url: str | None = typer.Option(None, "--git-url", help="Git clone URL"),
    github: str | None = typer.Option(None, "--github", help="GitHub OWNER/REPO"),
    bitbucket: str | None = typer.Option(
        None, "--bitbucket", help="Bitbucket WORKSPACE/REPO"
    ),
    hf: str | None = typer.Option(
        None, "--hf", help="Hugging Face Hub id (ORG/NAME or datasets|spaces/ORG/NAME)"
    ),
    ref: str | None = typer.Option(None, "--ref", help="Branch/tag for remotes"),
    mode: str = typer.Option("full", "--mode", help="full | diff"),
    since: str | None = typer.Option(None, "--since", help="Diff base ref"),
    out: Path | None = typer.Option(None, "--out", help="Report directory"),
    fmt: str = typer.Option("md", "--format", help="md | json | both"),
    model: str | None = typer.Option(None, "--model", help="Override model name"),
    fail_on: str | None = typer.Option(None, "--fail-on", help="Exit 1 severity threshold"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inventory only; no LLM call"),
    trust_project: bool = typer.Option(
        False,
        "--trust-project-config",
        help="Allow project .repolens.toml to set provider/base_url/api_key_env",
    ),
    scanners: str = typer.Option(
        "auto",
        "--scanners",
        help="auto | off | comma list (gitleaks,semgrep,osv,trivy,checkov)",
    ),
    require_scanners: bool = typer.Option(
        False, "--require-scanners", help="Exit 2 if a requested scanner is missing"
    ),
    scanners_only: bool = typer.Option(
        False, "--scanners-only", help="Skip LLM; report scanner findings only"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Hide progress status lines"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Extra progress detail (file sample, scanner status)"
    ),
    heartbeat: float = typer.Option(
        15.0,
        "--heartbeat",
        help="Seconds between LLM wait heartbeats (0 disables)",
    ),
    timeout: float | None = typer.Option(
        None,
        "--timeout",
        help="LLM HTTP timeout in seconds (default: 900 for ollama, 120 otherwise)",
    ),
    force_full: bool = option_force_full(),
    force_changed: bool = option_force_changed(),
    git_diff: str | None = option_git_diff(),
    deep: bool | None = typer.Option(
        None,
        "--deep/--no-deep",
        help="Multi-pass deep coverage (default: on; --no-deep = single-shot)",
    ),
    deep_passes: int | None = typer.Option(
        None,
        "--deep-passes",
        help="Cap deep band passes (1 = P1-only). Overrides [deep].max_passes.",
        min=1,
    ),
    ci: bool = typer.Option(
        False,
        "--ci",
        help="PR/CI recipe: triage routing, --changed pack, single-shot LLM on scanner hits only",
    ),
    sarif: bool = typer.Option(
        False,
        "--sarif",
        help="Write anchored SARIF 2.1 (scanner locations + resolvable anchors only)",
    ),
    verify_findings: bool | None = typer.Option(
        None,
        "--verify-findings/--no-verify-findings",
        help="Re-check Critical locations (non-fatal; default: [deep].verify_findings)",
    ),
    pack: list[str] | None = typer.Option(
        None,
        "--pack",
        help="Enable a domain pack (repeatable); see `repolens packs list`",
    ),
    fallback: bool = typer.Option(
        True,
        "--fallback/--no-fallback",
        help=(
            "Automatically fall back to local Ollama or SAST scanners "
            "when Cloud AI is unavailable"
        ),
    ),
    import_sarif: list[Path] | None = typer.Option(
        None,
        "--import-sarif",
        help="Merge findings from a SARIF 2.1 file (repeatable). Treated as scanner evidence.",
    ),
    require_sarif_import: bool = typer.Option(
        False,
        "--require-sarif-import",
        help=(
            "Exit 2 if any --import-sarif path is missing or unreadable "
            "(default: soft-fail and continue)"
        ),
    ),
) -> None:
    """Architecture / production-readiness audit."""
    _run_mode(
        "architecture",
        path,
        git_url,
        github,
        bitbucket,
        hf,
        ref,
        mode,
        since,
        out,
        fmt,
        model,
        fail_on,
        dry_run,
        True,
        trust_project,
        scanners,
        require_scanners,
        scanners_only,
        quiet,
        verbose,
        heartbeat,
        timeout,
        force_full,
        force_changed,
        git_diff,
        deep_passes,
        deep,
        None,
        ci,
        sarif,
        verify_findings,
        pack,
        fallback,
        False,
        import_sarif,
        require_sarif_import,
    )
