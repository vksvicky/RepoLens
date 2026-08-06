"""Domain packs CLI (Phase 6.10)."""

from __future__ import annotations

from rich.table import Table

from repolens.cli.app import console, packs_app
from repolens.packs import list_packs


@packs_app.command("list")
def packs_list_cmd() -> None:
    """List optional domain packs (off by default)."""
    table = Table(title="Domain packs")
    table.add_column("Id")
    table.add_column("Title")
    table.add_column("Description")
    for pack in list_packs():
        table.add_row(pack.id, pack.title, pack.description)
    console.print(table)
    console.print(
        "[dim]Enable with[/dim] [cyan]--pack <id>[/cyan] "
        "[dim]or[/dim] [cyan]\\[packs] enabled = [\"…\"][/cyan] "
        "[dim]in config — see[/dim] [cyan]docs/packs.md[/cyan]"
    )
