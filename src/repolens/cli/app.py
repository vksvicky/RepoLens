"""RepoLens CLI app shell, init, and shared helpers."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from repolens import __version__
from repolens.config import write_user_config
from repolens.sources import SourceError

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
adaptive_app = typer.Typer(
    name="adaptive",
    help="Per-project fingerprint cache and timeout recommendations.",
    no_args_is_help=True,
)
packs_app = typer.Typer(
    name="packs",
    help="Optional domain packs (Azure Sentinel / SOAR, …).",
    no_args_is_help=True,
)
app.add_typer(plugins_app, name="plugins")
app.add_typer(learn_app, name="learn")
app.add_typer(adaptive_app, name="adaptive")
app.add_typer(packs_app, name="packs")
console = Console(stderr=True)

_EMPTY_PATH_HELP = (
    "--path is empty. In bash/zsh assign without `set` or spaces around `=`: "
    "TARGET=/Users/[username]/Development/[your-project]  "
    "(not: set TARGET = …). Example: --path /Users/jackfrost/Development/acme-api"
)


def _coerce_local_path(path: str | Path | None) -> Path | None:
    """Convert CLI --path; reject empty strings (Path('') would silently become '.')."""
    if path is None:
        return None
    if isinstance(path, str) and not path.strip():
        raise SourceError(_EMPTY_PATH_HELP)
    return Path(path)


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
        help="openai | anthropic | deepseek | openai_compatible | ollama | none",
        prompt=(
            "Provider (openai / anthropic / deepseek / openai_compatible / ollama / none)"
        ),
    ),
    model: str | None = typer.Option(None, "--model", help="Default model name"),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="Override API base URL (required for most openai_compatible hosts)",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing user config"),
) -> None:
    """First-run setup: write ~/.config/repolens/config.toml (BYOK, Ollama, or scanners-only)."""
    from repolens.config import user_config_path

    provider = provider.strip().lower()
    allowed = {
        "openai",
        "anthropic",
        "deepseek",
        "openai_compatible",
        "ollama",
        "none",
    }
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
        # Escape hatch for Azure OpenAI, Groq, Mistral, OpenRouter, LM Studio, etc.
        "openai_compatible": (
            "gpt-4.1-mini",
            "REPOLENS_API_KEY",
            "https://api.openai.com/v1",
        ),
        "ollama": (None, None, "http://127.0.0.1:11434/v1"),
    }
    default_model, key_env, base = defaults[provider]
    chosen_model = model or default_model
    chosen_base = base_url or base
    if provider == "openai_compatible" and not base_url:
        console.print(
            "[yellow]openai_compatible[/yellow] usually needs "
            "[cyan]--base-url[/cyan] (e.g. Azure / Groq / OpenRouter / LM Studio). "
            f"Writing placeholder [dim]{chosen_base}[/dim] — edit config if wrong."
        )
    if provider == "ollama":
        from repolens.llm import resolve_ollama_model

        chosen_model, installed = resolve_ollama_model(model)
        if installed and (model is None or not model.strip()):
            console.print(
                f"[dim]Using installed Ollama model:[/dim] {chosen_model} "
                f"(from {', '.join(installed[:5])}"
                f"{'…' if len(installed) > 5 else ''})"
            )
        elif not installed:
            console.print(
                "[yellow]No Ollama models found.[/yellow] "
                f"Pull one first, e.g. [cyan]ollama pull {chosen_model}[/cyan], "
                "or pass [cyan]--model[/cyan] after pulling."
            )
    written = write_user_config(
        provider=provider,
        model=chosen_model,
        api_key_env=key_env,
        base_url=chosen_base,
    )
    console.print(f"[green]Wrote[/green] {written}")
    if key_env:
        console.print(f"Export your key: [cyan]export {key_env}=...[/cyan]")
    if provider == "ollama":
        console.print(
            f"Config model is [cyan]{chosen_model}[/cyan]. "
            "Change anytime with [cyan]repolens init --provider ollama --model NAME --force[/cyan] "
            "or edit the config file."
        )
    console.print("Try: [cyan]repolens review --path . --dry-run[/cyan]")
    console.print("Optional scanners: [cyan]repolens plugins status[/cyan]")




def run() -> None:
    app()


if __name__ == "__main__":
    app()
