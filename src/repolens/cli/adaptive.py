"""Local learning and adaptive-cache CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from repolens.cli.app import adaptive_app, console, learn_app

@learn_app.command("build")
def learn_build(
    path: Path = typer.Option(Path("."), "--path", help="Project root"),
    accept: bool = typer.Option(
        False,
        "--accept-local-learning",
        help="Record informed consent for on-disk local learning",
    ),
) -> None:
    """Build or rebuild the local keyword index under .repolens/."""
    from repolens.learning.consent import CONSENT_NOTICE
    from repolens.learning.index import LearningIndex

    root = path.resolve()
    if not accept:
        from repolens.learning.consent import has_consent

        if not has_consent(root):
            console.print(CONSENT_NOTICE)
            console.print(
                "[yellow]Re-run with[/yellow] [cyan]--accept-local-learning[/cyan] to consent."
            )
            raise typer.Exit(code=2)
    try:
        count = LearningIndex(root).build(accept=accept)
    except PermissionError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    from repolens.learning.store import store_db_path

    console.print(f"[green]Indexed[/green] {count} file(s) → {store_db_path(root)}")


@learn_app.command("status")
def learn_status(
    path: Path = typer.Option(Path("."), "--path", help="Project root"),
) -> None:
    """Show consent and index status."""
    from repolens.learning.consent import has_consent
    from repolens.learning.store import store_db_path

    root = path.resolve()
    db = store_db_path(root)
    table = Table(title="Local learning")
    table.add_column("Key")
    table.add_column("Value")
    table.add_row("Consent", "yes" if has_consent(root) else "no")
    table.add_row("Store", str(db) if db.is_file() else "missing")
    if db.is_file():
        table.add_row("Store size", f"{db.stat().st_size} bytes")
    console.print(table)


@adaptive_app.command("status")
def adaptive_status(
    path: Path = typer.Option(Path("."), "--path", help="Project root"),
) -> None:
    """Show fingerprint cache stats and recommended timeout."""
    from repolens.config import load_config
    from repolens.inventory import list_files
    from repolens.learning.store import ProjectStore, store_db_path

    root = path.resolve()
    cfg = load_config(root)
    db = store_db_path(root)
    table = Table(title="Adaptive cache")
    table.add_column("Key")
    table.add_column("Value")
    table.add_row("Enabled", "yes" if cfg.adaptive.enabled else "no")
    table.add_row("Mode", cfg.adaptive.mode)
    table.add_row("Store", str(db) if db.is_file() else "missing")
    if db.is_file():
        from repolens.adaptive import fingerprint_rows_from_entries

        with ProjectStore(root) as store:
            fps = store.list_fingerprints()
            rec = store.get_meta("recommended_timeout_seconds")
            runs = store.successful_llm_seconds(limit=5)
            files = list_files(root, mode="full")
            diff = store.diff_fingerprints(fingerprint_rows_from_entries(files))
        table.add_row("Fingerprints", str(len(fps)))
        table.add_row("Recommended timeout", f"{rec}s" if rec else "(none yet)")
        table.add_row("Recent LLM seconds", ", ".join(f"{x:.1f}" for x in runs) or "(none)")
        table.add_row(
            "Pending changes",
            f"+{len(diff.added)} ~{len(diff.changed)} -{len(diff.deleted)}",
        )
    console.print(table)


@learn_app.command("clear")
def learn_clear(
    path: Path = typer.Option(Path("."), "--path", help="Project root"),
) -> None:
    """Delete the local index database (consent file kept)."""
    from repolens.learning.index import clear_index

    root = path.resolve()
    clear_index(root)
    console.print(f"[green]Cleared index under[/green] {root / '.repolens'}")
