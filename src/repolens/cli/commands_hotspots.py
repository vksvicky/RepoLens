"""``repolens hotspots`` — git churn table (C7). No LLM."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from repolens.cli.app import app, console
from repolens.git_churn import GitChurnError, collect_git_hotspots


@app.command("hotspots")
def hotspots_cmd(
    path: Path = typer.Option(Path("."), "--path", help="Git repository root"),
    since: str = typer.Option("6.months", "--since", help="git log --since (allowlisted)"),
    fmt: str = typer.Option("", "--format", help="json for machine-readable rows"),
    limit: int = typer.Option(50, "--limit", help="Max paths"),
) -> None:
    """Print files with the most commits in the given window. No tree map."""
    root = path.resolve()
    try:
        rows = collect_git_hotspots(root, since=since.strip(), limit=limit)
    except GitChurnError as exc:
        msg = str(exc)
        console.print(f"[red]{msg}[/red]")
        if "unsafe since" in msg:
            raise typer.Exit(code=2) from exc
        raise typer.Exit(code=3) from exc

    if fmt.strip().lower() == "json":
        typer.echo(json.dumps(rows, indent=2))
        return
    if not rows:
        console.print("No churn in that window.")
        return
    console.print("path  commits  added  deleted")
    for row in rows:
        console.print(
            f"{row['path']}  {row['commits']}  {row['added']}  {row['deleted']}"
        )
