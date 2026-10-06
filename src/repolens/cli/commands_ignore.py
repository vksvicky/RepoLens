"""``repolens ignore add`` — append .repolens-ignore (C6)."""

from __future__ import annotations

from pathlib import Path

import typer

from repolens.cli.app import app, console
from repolens.suppressions import IGNORE_FILENAME, append_ignore_entry, load_ignore_file

ignore_app = typer.Typer(
    name="ignore",
    help="Write .repolens-ignore entries.",
    no_args_is_help=True,
)
app.add_typer(ignore_app, name="ignore")


@ignore_app.command("add")
def ignore_add(
    path: Path = typer.Option(Path("."), "--path"),
    rule_id: str | None = typer.Option(None, "--id", help="stableId"),
    file: str | None = typer.Option(None, "--file", help="Repo-relative path"),
    category: str | None = typer.Option(None, "--category"),
    reason: str = typer.Option("wont_fix", "--reason"),
    note: str = typer.Option("", "--note"),
) -> None:
    """Append one ignore row. Need --id or --file plus --category."""
    root = path.resolve()
    try:
        out = append_ignore_entry(
            root,
            stable_id=rule_id,
            file=file,
            category=category,
            reason=reason,
            note=note,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    console.print(f"[green]Wrote[/green] {out}")


@ignore_app.command("list")
def ignore_list(
    path: Path = typer.Option(Path("."), "--path"),
) -> None:
    """List active entries in ``.repolens-ignore``."""
    root = path.resolve()
    ignore_path = root / IGNORE_FILENAME
    if not ignore_path.is_file():
        console.print(f"[dim]No {IGNORE_FILENAME} at {root}[/dim]")
        raise typer.Exit(code=0)
    try:
        entries = load_ignore_file(root)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    active = [e for e in entries if e.active_on()]
    console.print(f"{ignore_path} — {len(active)} active / {len(entries)} total")
    for entry in entries:
        status = "active" if entry.active_on() else "expired"
        target = entry.stable_id or f"{entry.file}+{entry.category}"
        console.print(f"  [{status}] {target} reason={entry.reason}")
