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
from repolens.pipeline import fail_on_triggered, run_review
from repolens.schema import FindingReport

app = typer.Typer(
    name="repolens",
    help="Structured security and architecture reviews for any repository.",
    no_args_is_help=True,
)
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
        # Playbooks / dry-run path until Phase 3 scanners land.
        written = write_user_config(provider=None)
        console.print(f"[green]Wrote[/green] {written}")
        console.print(
            "No AI provider configured. Use [cyan]--dry-run[/cyan], playbooks manually, "
            "or re-run [cyan]repolens init --provider ollama|openai[/cyan]. "
            "See docs/setup-ai-and-scanners.md"
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


def _run_mode(
    mode: str,
    path: Path,
    review_mode: str,
    since: str | None,
    out: Path | None,
    fmt: str,
    model: str | None,
    fail_on: str | None,
    dry_run: bool,
    full_audit: bool,
    trust_project: bool,
) -> None:
    root = path.resolve()
    if not root.exists():
        console.print(f"[red]Path not found:[/red] {root}")
        raise typer.Exit(code=2)

    if fmt not in {"md", "json", "both"}:
        console.print("[red]--format must be md | json | both[/red]")
        raise typer.Exit(code=2)

    try:
        result = run_review(
            path=root,
            mode=mode,
            review_mode=review_mode,
            since=since,
            out_dir=out,
            fmt=fmt,
            model_override=model,
            full_audit=full_audit,
            dry_run=dry_run,
            trust_project=trust_project,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]Config/source error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    except ValueError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    except LlmError as exc:
        console.print(f"[red]Model error:[/red] {exc}")
        console.print("Run [cyan]repolens init[/cyan] or see docs/setup-ai-and-scanners.md")
        raise typer.Exit(code=4) from exc
    except RuntimeError as exc:
        console.print(f"[red]Source error:[/red] {exc}")
        raise typer.Exit(code=3) from exc

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
    path: Path = typer.Option(Path("."), "--path", help="Local project root"),
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
) -> None:
    """Full P1→P2→P3 dual review."""
    _run_mode(
        "review", path, mode, since, out, fmt, model, fail_on, dry_run, full_audit, trust_project
    )


@app.command()
def sentinel(
    path: Path = typer.Option(Path("."), "--path", help="Local project root"),
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
) -> None:
    """Security-only review (P1 playbook)."""
    _run_mode(
        "sentinel", path, mode, since, out, fmt, model, fail_on, dry_run, False, trust_project
    )


@app.command()
def architecture(
    path: Path = typer.Option(Path("."), "--path", help="Local project root"),
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
) -> None:
    """Architecture / production-readiness audit."""
    _run_mode(
        "architecture", path, mode, since, out, fmt, model, fail_on, dry_run, True, trust_project
    )


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
    console.print(table)


def run() -> None:
    app()


if __name__ == "__main__":
    app()
