"""RepoLens CLI entrypoint."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from repolens import __version__
from repolens.config import write_user_config
from repolens.llm import LlmError
from repolens.pipeline import ScannerRequirementError, fail_on_triggered, run_review
from repolens.plugins import install_plugins, plugin_status
from repolens.schema import FindingReport
from repolens.sources import SourceError, cleanup_source, resolve_source, select_source

app = typer.Typer(
    name="repolens",
    help="Structured security and architecture reviews for any repository.",
    no_args_is_help=True,
)
plugins_app = typer.Typer(
    name="plugins",
    help="Manage optional scanner plugins (gitleaks, Semgrep, OSV-Scanner).",
    no_args_is_help=True,
)
learn_app = typer.Typer(
    name="learn",
    help="Opt-in local learning (on-disk index + memory).",
    no_args_is_help=True,
)
app.add_typer(plugins_app, name="plugins")
app.add_typer(learn_app, name="learn")
console = Console(stderr=True)


@app.callback()
def main() -> None:
    """RepoLens CLI."""


@app.command()
def version() -> None:
    """Print RepoLens version."""
    typer.echo(__version__)


@app.command("init")
def init_cmd(
    provider: str = typer.Option(
        ...,
        "--provider",
        help="openai | anthropic | deepseek | ollama | none",
        prompt="Provider (openai / anthropic / deepseek / ollama / none)",
    ),
    model: str | None = typer.Option(None, "--model", help="Default model name"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing user config"),
) -> None:
    """First-run setup: write ~/.config/repolens/config.toml (BYOK, Ollama, or scanners-only)."""
    from repolens.config import user_config_path

    provider = provider.strip().lower()
    allowed = {"openai", "anthropic", "deepseek", "ollama", "none"}
    if provider not in allowed:
        console.print(f"[red]Unknown provider:[/red] {provider}. Choose from {sorted(allowed)}")
        raise typer.Exit(code=2)

    path = user_config_path()
    if path.exists() and not force:
        console.print(f"[yellow]Config already exists:[/yellow] {path}")
        console.print("Re-run with --force to overwrite, or edit the file manually.")
        raise typer.Exit(code=2)

    if provider == "none":
        written = write_user_config(provider=None)
        console.print(f"[green]Wrote[/green] {written}")
        console.print(
            "No AI provider configured. Use [cyan]--dry-run[/cyan], "
            "[cyan]--scanners-only[/cyan] after [cyan]repolens plugins install[/cyan], "
            "or re-run [cyan]repolens init --provider ollama|openai[/cyan]. "
            "See docs/setup-ai-and-scanners.md and docs/scanners.md"
        )
        return

    defaults = {
        "openai": ("gpt-4.1-mini", "OPENAI_API_KEY", None),
        "anthropic": ("claude-sonnet-4-20250514", "ANTHROPIC_API_KEY", None),
        "deepseek": ("deepseek-chat", "DEEPSEEK_API_KEY", "https://api.deepseek.com/v1"),
        "ollama": ("llama3.1", None, "http://127.0.0.1:11434/v1"),
    }
    default_model, key_env, base = defaults[provider]
    written = write_user_config(
        provider=provider,
        model=model or default_model,
        api_key_env=key_env,
        base_url=base,
    )
    console.print(f"[green]Wrote[/green] {written}")
    if key_env:
        console.print(f"Export your key: [cyan]export {key_env}=...[/cyan]")
    if provider == "ollama":
        console.print(
            "Ensure Ollama is running and the model is pulled "
            "(see docs/setup-ai-and-scanners.md)."
        )
    console.print("Try: [cyan]repolens review --path . --dry-run[/cyan]")
    console.print("Optional scanners: [cyan]repolens plugins status[/cyan]")


def _run_mode(
    mode: str,
    path: Path | None,
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
) -> None:
    if fmt not in {"md", "json", "both"}:
        console.print("[red]--format must be md | json | both[/red]")
        raise typer.Exit(code=2)

    if scanners_only and dry_run:
        console.print("[red]--scanners-only cannot be combined with --dry-run[/red]")
        raise typer.Exit(code=2)

    resolved = None
    try:
        try:
            kind, value = select_source(
                path=path,
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

        console.print(f"[dim]Source:[/dim] {resolved.label}")

        result = run_review(
            path=resolved.root,
            mode=mode,
            review_mode=review_mode,
            since=since,
            out_dir=out_dir,
            fmt=fmt,
            model_override=model,
            full_audit=full_audit,
            dry_run=dry_run,
            trust_project=trust_project,
            scanners=scanners,
            require_scanners=require_scanners,
            scanners_only=scanners_only,
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
        console.print(f"[red]Model error:[/red] {exc}")
        console.print("Run [cyan]repolens init[/cyan] or see docs/setup-ai-and-scanners.md")
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

    try:
        triggered = fail_on_triggered(result.report, fail_on)
    except ValueError as exc:
        console.print(f"[red]Usage error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    if triggered:
        raise typer.Exit(code=1)


@app.command()
def review(
    path: Path | None = typer.Option(None, "--path", help="Local project root (default: .)"),
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
        "auto", "--scanners", help="auto | off | comma list (gitleaks,semgrep,osv)"
    ),
    require_scanners: bool = typer.Option(
        False, "--require-scanners", help="Exit 2 if a requested scanner is missing"
    ),
    scanners_only: bool = typer.Option(
        False, "--scanners-only", help="Skip LLM; report scanner findings only"
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
    )


@app.command()
def sentinel(
    path: Path | None = typer.Option(None, "--path", help="Local project root (default: .)"),
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
        "auto", "--scanners", help="auto | off | comma list (gitleaks,semgrep,osv)"
    ),
    require_scanners: bool = typer.Option(
        False, "--require-scanners", help="Exit 2 if a requested scanner is missing"
    ),
    scanners_only: bool = typer.Option(
        False, "--scanners-only", help="Skip LLM; report scanner findings only"
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
    )


@app.command()
def architecture(
    path: Path | None = typer.Option(None, "--path", help="Local project root (default: .)"),
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
        "auto", "--scanners", help="auto | off | comma list (gitleaks,semgrep,osv)"
    ),
    require_scanners: bool = typer.Option(
        False, "--require-scanners", help="Exit 2 if a requested scanner is missing"
    ),
    scanners_only: bool = typer.Option(
        False, "--scanners-only", help="Skip LLM; report scanner findings only"
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
    )


@plugins_app.command("status")
def plugins_status_cmd() -> None:
    """Show which scanner plugins are available (PATH or cache)."""
    table = Table(title="Scanner plugins")
    table.add_column("Tool")
    table.add_column("State")
    table.add_column("Detail")
    for tool, state, detail in plugin_status():
        colour = "green" if state == "available" else "yellow"
        table.add_row(tool, f"[{colour}]{state}[/{colour}]", detail)
    console.print(table)


@plugins_app.command("list")
def plugins_list_cmd() -> None:
    """List known scanner plugins (alias of status)."""
    plugins_status_cmd()


@plugins_app.command("install")
def plugins_install_cmd(
    tools: list[str] = typer.Argument(
        None, help="Plugin names or 'all' (default: all)"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip consent prompts (CI / non-interactive)"
    ),
) -> None:
    """Download pinned scanner binaries into ~/.cache/repolens/tools/ (with consent)."""
    selected = tools or ["all"]
    try:
        messages = install_plugins(selected, yes=yes)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    for msg in messages:
        console.print(msg)
    if any("failed" in m or "skipped (declined)" in m for m in messages):
        # Partial success still exits 0 unless everything failed hard without install
        pass


@learn_app.command("build")
def learn_build(
    path: Path = typer.Option(Path("."), "--path", help="Project root"),
    accept: bool = typer.Option(
        False,
        "--accept-local-learning",
        help="Record informed consent for on-disk local learning",
    ),
) -> None:
    """Build or rebuild the local keyword index under .repolens/."""
    from repolens.learning.consent import CONSENT_NOTICE
    from repolens.learning.index import LearningIndex

    root = path.resolve()
    if not accept:
        from repolens.learning.consent import has_consent

        if not has_consent(root):
            console.print(CONSENT_NOTICE)
            console.print(
                "[yellow]Re-run with[/yellow] [cyan]--accept-local-learning[/cyan] to consent."
            )
            raise typer.Exit(code=2)
    try:
        count = LearningIndex(root).build(accept=accept)
    except PermissionError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    console.print(f"[green]Indexed[/green] {count} file(s) → {root / '.repolens' / 'index.sqlite'}")


@learn_app.command("status")
def learn_status(
    path: Path = typer.Option(Path("."), "--path", help="Project root"),
) -> None:
    """Show consent and index status."""
    from repolens.learning.consent import has_consent
    from repolens.learning.index import index_db_path

    root = path.resolve()
    db = index_db_path(root)
    table = Table(title="Local learning")
    table.add_column("Key")
    table.add_column("Value")
    table.add_row("Consent", "yes" if has_consent(root) else "no")
    table.add_row("Index", str(db) if db.is_file() else "missing")
    if db.is_file():
        table.add_row("Index size", f"{db.stat().st_size} bytes")
    console.print(table)


@learn_app.command("clear")
def learn_clear(
    path: Path = typer.Option(Path("."), "--path", help="Project root"),
) -> None:
    """Delete the local index database (consent file kept)."""
    from repolens.learning.index import clear_index

    root = path.resolve()
    clear_index(root)
    console.print(f"[green]Cleared index under[/green] {root / '.repolens'}")


@app.command()
def export(
    report: Path = typer.Argument(..., exists=True, readable=True, help="Markdown report path"),
    pdf: bool = typer.Option(False, "--pdf", help="Convert with pandoc if available"),
) -> None:
    """Export or convert an existing report."""
    typer.echo(f"Report: {report.resolve()}")
    if not pdf:
        return
    pandoc = shutil.which("pandoc")
    if not pandoc:
        console.print(
            "[yellow]pandoc not found.[/yellow] Install pandoc or use Print → Save as PDF."
        )
        raise typer.Exit(code=2)
    out = report.with_suffix(".pdf")
    completed = subprocess.run([pandoc, str(report), "-o", str(out)], check=False)
    if completed.returncode != 0:
        console.print("[red]pandoc failed[/red]")
        raise typer.Exit(code=2)
    console.print(f"[green]PDF:[/green] {out}")


def _print_summary(confidence: int, files: int, report: FindingReport, *, dry_run: bool) -> None:
    table = Table(title="RepoLens summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Dry run", "yes" if dry_run else "no")
    table.add_row("Files scanned", str(files))
    table.add_row("Confidence", f"{confidence}%")
    table.add_row("Critical", str(report.summary.critical))
    table.add_row("High", str(report.summary.high))
    table.add_row("Medium", str(report.summary.medium))
    table.add_row("Low", str(report.summary.low))
    if report.scannerRuns:
        ran = sum(1 for r in report.scannerRuns if r.status == "ran")
        table.add_row("Scanners ran", f"{ran}/{len(report.scannerRuns)}")
    console.print(table)


def run() -> None:
    app()


if __name__ == "__main__":
    app()
