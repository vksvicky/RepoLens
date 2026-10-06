"""``repolens duplicates`` — near-clone spans for an editor diff (C5)."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from repolens.cli.app import app, console
from repolens.config import load_config
from repolens.heuristics.near_clones import find_near_clones
from repolens.inventory import scan_inventory


@app.command("duplicates")
def duplicates_cmd(
    path: Path = typer.Option(Path("."), "--path"),
    file: str | None = typer.Option(None, "--file", help="Restrict to this repo-relative path"),
    fmt: str = typer.Option("", "--format", help="json for machine-readable spans"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Print near-clone file pairs and line spans. No LLM."""
    root = path.resolve()
    cfg = load_config(root)
    inv = scan_inventory(
        root,
        mode="full",
        max_files=cfg.fast_brain.max_files,
        skip_globs=cfg.deep.skip_paths,
    )
    result = find_near_clones(inv.files, config=cfg.fast_brain.near_clones)
    want = file.replace("\\", "/").lstrip("./") if file else None
    rows = []
    for issue in result.issues:
        rel = issue.file.replace("\\", "/")
        if want and rel != want and not rel.endswith("/" + want):
            continue
        rows.append(
            {
                "file": issue.file,
                "line": issue.line,
                "title": issue.title,
                "message": issue.explanation[:400],
            }
        )
    emit_json = as_json or fmt.strip().lower() == "json"
    if emit_json:
        typer.echo(json.dumps(rows, indent=2))
        return
    if not rows:
        console.print("No near-clone clusters in the inventory pack.")
        return
    for row in rows:
        console.print(f"{row['file']}:{row['line']}  {row['title']}")
