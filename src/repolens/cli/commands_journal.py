"""``repolens journal`` — honesty metrics from journal.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from repolens.cli.app import app, console
from repolens.pipeline.journal import (
    build_postmortem,
    journal_path,
    postmortem_data,
    read_events,
)


@app.command("journal")
def journal_cmd(
    path: Path = typer.Option(Path("."), "--path", help="Project root"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON"),
) -> None:
    """Post-mortem + chars_in/chars_out from journal.jsonl. No Metis % claim."""
    root = path.resolve()
    events = read_events(root)
    if as_json:
        data = postmortem_data(root)
        chars = data.get("chars") or {}
        payload = {
            "pass_completed": chars.get("pass_completed", 0),
            "resumed": chars.get("resumed", 0),
            "chars_in": chars.get("chars_in", 0),
            "chars_out": chars.get("chars_out", 0),
            "last_finished": data.get("last_finished"),
            "events": data.get("events", 0),
            "run_id": data.get("run_id"),
            "status": data.get("status"),
            "role_packs": data.get("role_packs"),
            "interrupted_during": data.get("interrupted_during"),
            "completed_passes": data.get("completed_passes"),
            "verify": data.get("verify"),
        }
        typer.echo(json.dumps(payload, indent=2, default=str))
        return
    if not events:
        console.print(f"No journal at {journal_path(root)}")
        return
    console.print(build_postmortem(root))
