"""``repolens blast-radius`` — transitive consumer simulation."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer
from rich.table import Table

from repolens.blast_radius import simulate_blast_radius
from repolens.cli.app import app, console
from repolens.cli.exit_codes import EXIT_BAD_INPUT, JSON_INDENT
from repolens.cli.pack_scope import option_path

_CONSUMER_PREVIEW = 40


@app.command("blast-radius")
def blast_radius_cmd(
    seed: str = typer.Argument(..., help="File path (pkg/core.py) or dotted module (pkg.core)"),
    path: str | None = option_path(),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON"),
) -> None:
    """Show transitive importers, percent of graph, boundary hits, and test density."""
    root = Path(path or ".").resolve()
    try:
        sim = simulate_blast_radius(root, seed)
    except (OSError, ValueError, RuntimeError) as exc:
        console.print(f"[red]blast-radius failed:[/red] {exc}")
        raise typer.Exit(code=EXIT_BAD_INPUT) from exc

    if as_json:
        typer.echo(json.dumps(asdict(sim), indent=JSON_INDENT))
        return

    table = Table(title="blast-radius")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Seed", sim.seed)
    table.add_row("Module", sim.seed_module)
    table.add_row("Consumers", str(sim.consumer_count))
    table.add_row("% of graph", f"{sim.percent_of_graph}% of {sim.graph_module_count}")
    table.add_row("Boundary violations", str(len(sim.boundary_violations)))
    table.add_row("Test density", sim.test_density_note)
    console.print(table)
    if sim.consumers:
        console.print("[bold]Consumers[/bold]")
        for mod in sim.consumers[:_CONSUMER_PREVIEW]:
            console.print(f"  · {mod}")
        if len(sim.consumers) > _CONSUMER_PREVIEW:
            console.print(f"  … +{len(sim.consumers) - _CONSUMER_PREVIEW} more")
    for row in sim.boundary_violations[:20]:
        console.print(f"[yellow]boundary[/yellow] {row}")
    if sim.note:
        console.print(f"[dim]{sim.note}[/dim]")
