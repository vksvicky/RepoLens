"""``repolens journal`` — honesty metrics from journal.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from repolens.cli.app import app, console
from repolens.pipeline.journal import last_finished_label, read_events, summarize_chars


@app.command("journal")
def journal_cmd(
    path: Path = typer.Option(Path("."), "--path", help="Project root"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON"),
) -> None:
    """Sum chars_in/chars_out from .repolens/journal.jsonl. No Metis % claim."""
    root = path.resolve()
    totals = summarize_chars(root)
    last = last_finished_label(root)
    events = read_events(root)
    payload = {**totals, "last_finished": last, "events": len(events)}
    if as_json:
        typer.echo(json.dumps(payload, indent=2))
        return
    if not events:
        console.print(f"No journal at {root / '.repolens' / 'journal.jsonl'}")
        return
    console.print(
        f"Journal: {payload['events']} event(s) · "
        f"pass_completed={totals['pass_completed']} "
        f"(resumed={totals['resumed']}) · "
        f"chars_in={totals['chars_in']:,} chars_out={totals['chars_out']:,}"
    )
    if last:
        console.print(f"Last finished pass: {last}")
    console.print(
        "Honesty metric from this tree only — not a Metis token-cut percentage."
    )
