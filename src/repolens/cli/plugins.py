"""Plugin management CLI commands."""

from __future__ import annotations

import typer
from rich.table import Table

from repolens.cli.app import console, plugins_app
from repolens.plugins import install_plugins, plugin_status

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
