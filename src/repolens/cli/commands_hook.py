"""``repolens hook`` — checks a local git hook can run."""

from __future__ import annotations

from pathlib import Path

import typer

from repolens.cli.app import app
from repolens.fast_hook import blocking_lines

hook_app = typer.Typer(
    name="hook",
    help="Checks meant for a git hook. No model and no scanner binaries.",
    no_args_is_help=True,
)
app.add_typer(hook_app, name="hook")


@hook_app.command("fast")
def fast(
    path: Path = typer.Option(Path("."), "--path", help="Repository to check"),
) -> None:
    """Fast Brain on the whole tree. Exit 1 at MEDIUM. Leaves no report behind."""
    lines = blocking_lines(path.resolve())
    for line in lines:
        typer.echo(line)
    if lines:
        raise typer.Exit(code=1)
