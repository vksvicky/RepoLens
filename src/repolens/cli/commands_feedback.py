"""Local feedback → ``.repolens-ignore`` (Phase 6.7). No cloud upload."""

from __future__ import annotations

from pathlib import Path

import typer

from repolens.cli.app import app, console
from repolens.feedback_store import lookup_issue_meta, record_feedback
from repolens.suppressions import IGNORE_FILENAME, append_ignore_entry, load_ignore_file

feedback_app = typer.Typer(
    name="feedback",
    help="Local-only finding feedback (writes .repolens-ignore).",
    no_args_is_help=True,
)
app.add_typer(feedback_app, name="feedback")

_REASONS = ("false_positive", "wont_fix", "accepted_risk", "other")


@feedback_app.command("down")
def feedback_down(
    stable_id: str = typer.Argument(
        ..., help="Issue Fingerprint from a report (JSON: stableId)"
    ),
    reason: str = typer.Option(
        "false_positive",
        "--reason",
        help="false_positive | wont_fix | accepted_risk | other",
    ),
    note: str = typer.Option("", "--note", help="Optional audit note"),
    path: Path = typer.Option(Path("."), "--path", help="Project root"),
    expires: str | None = typer.Option(
        None,
        "--expires",
        help="Optional ISO date (YYYY-MM-DD) when the ignore expires",
    ),
) -> None:
    """Thumbs-down: append a Fingerprint ignore entry (local file only)."""
    reason = reason.strip().lower()
    if reason not in _REASONS:
        console.print(f"[red]Unknown reason:[/red] {reason}. Choose from {_REASONS}")
        raise typer.Exit(code=2)
    root = path.resolve()
    meta = lookup_issue_meta(root, stable_id.strip())
    try:
        written = append_ignore_entry(
            root,
            stable_id=stable_id.strip(),
            reason=reason,
            note=note.strip(),
            expires=expires,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    fb_path = record_feedback(
        root,
        stable_id=stable_id.strip(),
        reason=reason,
        category=meta.get("category", ""),
        file=meta.get("file", ""),
        title=meta.get("title", ""),
        note=note.strip(),
    )
    console.print(f"[green]Wrote[/green] ignore entry → {written}")
    console.print(f"[green]Logged[/green] feedback event → {fb_path}")
    if reason == "false_positive" and meta.get("category"):
        console.print(
            "[dim]Future reviews may soft-demote matching LLM/heuristic findings "
            f"(category `{meta['category']}`). Scanners still need an ignore entry.[/dim]"
        )
    console.print(
        "[dim]Suppressed findings are excluded from fail-on and SARIF on the next review. "
        "No data is uploaded.[/dim]"
    )


@feedback_app.command("list")
def feedback_list(
    path: Path = typer.Option(Path("."), "--path", help="Project root"),
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
        exp = f" expires={entry.expires.isoformat()}" if entry.expires else ""
        console.print(f"  [{status}] {target} reason={entry.reason}{exp}")
