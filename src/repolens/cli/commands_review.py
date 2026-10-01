"""Review / sentinel / architecture CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from repolens.cli.app import _coerce_local_path, app, console
from repolens.cli.commands_review_support import (
    _map_run_mode_error,
    _ratchet_breached_for_review,
)
from repolens.cli.export import _print_summary
from repolens.cli.pack_scope import (
    option_force_changed,
    option_force_full,
    option_git_diff,
)
from repolens.pipeline import fail_on_triggered, run_review
from repolens.progress import ReviewProgress
from repolens.sources import SourceError, cleanup_source, resolve_source, select_source


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
) -> None:
    resolved = None

    def _reject_run_flags():
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
            console.print(
                "[red]--model-lock and --no-model-lock cannot be combined[/red]"
            )
            raise typer.Exit(code=2)

    def _execute_run_mode():
        nonlocal resolved
        ratchet_breached = False
        try:
            local_path = _coerce_local_path(path)
            kind, value = select_source(
                path=local_path,
                git_url=git_url,
                github=github,
                bitbucket=bitbucket,
                hf=hf,
            )
            resolved = resolve_source(kind=kind, value=value, ref=ref)
        except SourceError as exc:
            # Clone/auth failures → 3; usage / missing path / bad slug → 2
            msg = str(exc)
            code = 3 if msg.startswith("Clone failed") else 2
            console.print(f"[red]Source error:[/red] {exc}")
            raise typer.Exit(code=code) from None

        out_dir = out
        if out_dir is None and resolved.ephemeral:
            out_dir = Path.cwd() / "reports"

        if not quiet:
            console.print(f"[dim]Source:[/dim] {resolved.label}")

        result = run_review(
            path=resolved.root,
            mode=mode,
            review_mode=review_mode,
            since=since,
            out_dir=out_dir,
            fmt=fmt,
            model_override=model,
            timeout_override=timeout,
            force_full=force_full,
            force_changed=force_changed,
            git_diff=git_diff,
            deep_passes=deep_passes,
            full_audit=full_audit,
            dry_run=dry_run,
            trust_project=trust_project,
            scanners=scanners,
            require_scanners=require_scanners,
            scanners_only=scanners_only,
            progress=progress,
            deep=deep,
            ci=ci,
            sarif=sarif,
            verify_findings=verify_findings,
            packs=packs,
            fallback=fallback,
            import_sarif=import_sarif or [],
            require_sarif_import=require_sarif_import,
            model_lock=model_lock,
        )

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

        if explain_uuids and not result.dry_run:
            from repolens.cli.commands_explain import run_post_review_explains

            run_post_review_explains(explain_uuids, path=path, result=result)

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
        if not result.dry_run and mode == "review":
            ratchet_breached = _ratchet_breached_for_review(
                resolved.root, ratchet_flag=ratchet
            )

        if triggered or ratchet_breached:
            raise typer.Exit(code=1)


    _reject_run_flags()
    progress = ReviewProgress(
        quiet=quiet,
        verbose=verbose,
        heartbeat_seconds=heartbeat,
        console=console,
    )
    try:
        _execute_run_mode()
    except typer.Exit:
        raise
    except Exception as exc:
        _map_run_mode_error(exc)
        raise
    finally:
        if resolved is not None:
            cleanup_source(resolved)


@app.command()
def review(
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
    fail_on: str | None = typer.Option(
        None, "--fail-on", help="Exit 1 if findings at/above severity"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inventory only; no LLM call"),
    full_audit: bool = typer.Option(
        False, "--full-audit", help="Include full architecture playbook"
    ),
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
        help="Seconds to wait for the first model token (default: 900 for ollama, 120 otherwise)",
    ),
    model_lock_flag: bool = typer.Option(
        False,
        "--model-lock",
        help="Force the local model queue on, including for a cloud URL",
    ),
    no_model_lock: bool = typer.Option(
        False,
        "--no-model-lock",
        help="Allow concurrent calls to a local one-model server",
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
    explain: str | None = typer.Option(
        None,
        "--explain",
        help=(
            "After review, deep-dive these UUID(s) "
            "(Fingerprint or Occurrence, comma-separated)"
        ),
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
    ratchet: bool = typer.Option(
        False,
        "--ratchet",
        help=(
            "Exit 1 if runtime cyclicity exceeds the baseline "
            "(also enabled by [graph].ratchet; combines with --fail-on)"
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
    """Full P1→P2→P3 dual review."""
    _run_mode(
        "review",
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
        full_audit,
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
        explain,
        ci,
        sarif,
        verify_findings,
        pack,
        fallback,
        ratchet,
        import_sarif,
        require_sarif_import,
        no_model_lock,
        True if model_lock_flag else False if no_model_lock else None,
    )


