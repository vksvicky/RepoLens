"""Review / sentinel / architecture CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from repolens.cli.app import _coerce_local_path, app, console
from repolens.cli.export import _print_summary
from repolens.llm import LlmError
from repolens.pipeline import ScannerRequirementError, fail_on_triggered, run_review
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
    deep: bool | None = None,
    explain_uuids: str | None = None,
    ci: bool = False,
    sarif: bool = False,
    verify_findings: bool | None = None,
) -> None:
    if fmt not in {"md", "json", "both"}:
        console.print("[red]--format must be md | json | both[/red]")
        raise typer.Exit(code=2)

    if scanners_only and dry_run:
        console.print("[red]--scanners-only cannot be combined with --dry-run[/red]")
        raise typer.Exit(code=2)

    if force_full and force_changed:
        console.print("[red]--full and --changed cannot be combined[/red]")
        raise typer.Exit(code=2)

    if quiet and verbose:
        console.print("[red]--quiet and --verbose cannot be combined[/red]")
        raise typer.Exit(code=2)

    progress = ReviewProgress(
        quiet=quiet,
        verbose=verbose,
        heartbeat_seconds=heartbeat,
        console=console,
    )

    resolved = None
    try:
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
        )
    except FileNotFoundError as exc:
        console.print(f"[red]Config/source error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    except ValueError as exc:
        console.print(f"[red]Config/usage error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    except ScannerRequirementError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print("Install with [cyan]repolens plugins install[/cyan] or see docs/scanners.md")
        raise typer.Exit(code=2) from exc
    except LlmError as exc:
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
    except typer.Exit:
        raise
    except RuntimeError as exc:
        console.print(f"[red]Source error:[/red] {exc}")
        raise typer.Exit(code=3) from None
    finally:
        if resolved is not None:
            cleanup_source(resolved)

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
    if triggered:
        raise typer.Exit(code=1)


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
        help="LLM HTTP timeout in seconds (default: 900 for ollama, 120 otherwise)",
    ),
    force_full: bool = typer.Option(
        False,
        "--full",
        help="Force full LLM file pack (ignore adaptive changed-only selection)",
    ),
    force_changed: bool = typer.Option(
        False,
        "--changed",
        help="LLM pack = added/changed files only (skip LLM if none)",
    ),
    deep: bool | None = typer.Option(
        None,
        "--deep/--no-deep",
        help="Multi-pass deep coverage (default: on; --no-deep = single-shot)",
    ),
    explain: str | None = typer.Option(
        None,
        "--explain",
        help="After review, deep-dive these issue UUID(s) (comma-separated runId/stableId)",
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
        deep,
        explain,
        ci,
        sarif,
        verify_findings,
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
    force_full: bool = typer.Option(
        False,
        "--full",
        help="Force full LLM file pack (ignore adaptive changed-only selection)",
    ),
    force_changed: bool = typer.Option(
        False,
        "--changed",
        help="LLM pack = added/changed files only (skip LLM if none)",
    ),
    deep: bool | None = typer.Option(
        None,
        "--deep/--no-deep",
        help="Multi-pass deep coverage (default: on; --no-deep = single-shot)",
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
        deep,
        None,
        ci,
        sarif,
        verify_findings,
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
    force_full: bool = typer.Option(
        False,
        "--full",
        help="Force full LLM file pack (ignore adaptive changed-only selection)",
    ),
    force_changed: bool = typer.Option(
        False,
        "--changed",
        help="LLM pack = added/changed files only (skip LLM if none)",
    ),
    deep: bool | None = typer.Option(
        None,
        "--deep/--no-deep",
        help="Multi-pass deep coverage (default: on; --no-deep = single-shot)",
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
        deep,
        None,
        ci,
        sarif,
        verify_findings,
    )
