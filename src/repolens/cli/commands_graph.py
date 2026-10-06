"""``repolens graph`` — query the Python import graph (C2)."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from repolens.cli.app import app, console
from repolens.config import load_config
from repolens.graph import analyse_python_graph
from repolens.graph.query import (
    direct_dependencies,
    direct_dependents,
    would_create_cycle,
)
from repolens.graph.types import GraphStatus

graph_app = typer.Typer(
    name="graph",
    help="Python import-graph queries (no LLM).",
    no_args_is_help=True,
)
app.add_typer(graph_app, name="graph")


def _graph(root: Path):
    cfg = load_config(root)
    result = analyse_python_graph(root, config=cfg.graph)
    if result.status != GraphStatus.OK:
        console.print("[red]Graph analysis not OK[/red]")
        for gap in result.durability_gaps:
            console.print(f"  {gap}")
        raise typer.Exit(code=3)
    return result


def _emit(rows: object, *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(rows, indent=2))
        return
    if isinstance(rows, list):
        if not rows:
            console.print("(none)")
            return
        for row in rows:
            console.print(row if isinstance(row, str) else json.dumps(row))
        return
    typer.echo(json.dumps(rows, indent=2))


@graph_app.command("deps")
def graph_deps(
    module: str = typer.Argument(..., help="Importer module, e.g. packcycle.a"),
    path: Path = typer.Option(Path("."), "--path"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Direct imports of MODULE."""
    _emit(direct_dependencies(_graph(path.resolve()), module), as_json=as_json)


@graph_app.command("dependents")
def graph_dependents(
    module: str = typer.Argument(..., help="Imported module"),
    path: Path = typer.Option(Path("."), "--path"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Modules that import MODULE."""
    _emit(direct_dependents(_graph(path.resolve()), module), as_json=as_json)


@graph_app.command("cycles")
def graph_cycles(
    path: Path = typer.Option(Path("."), "--path"),
    fmt: str = typer.Option("json", "--format", help="json"),
) -> None:
    """Cycle groups plus cyclicity. JSON on stdout."""
    if fmt.strip().lower() != "json":
        console.print("[red]--format must be json[/red]")
        raise typer.Exit(code=2)
    result = _graph(path.resolve())
    payload = {
        "cyclicity": result.cyclicity,
        "cycleCount": len(result.cycles),
        "cycles": [{"modules": list(c.modules)} for c in result.cycles],
    }
    typer.echo(json.dumps(payload, indent=2))


@graph_app.command("edges")
def graph_edges(
    path: Path = typer.Option(Path("."), "--path"),
    fmt: str = typer.Option("json", "--format", help="json"),
) -> None:
    """Gated import edges (importer, imported, kind, line). JSON on stdout."""
    if fmt.strip().lower() != "json":
        console.print("[red]--format must be json[/red]")
        raise typer.Exit(code=2)
    result = _graph(path.resolve())
    rows = [
        {
            "importer": e.importer,
            "imported": e.imported,
            "kind": str(e.kind),
            "line": e.line,
        }
        for e in result.gated_edges
    ]
    typer.echo(json.dumps(rows, indent=2))


@graph_app.command("would-cycle")
def graph_would_cycle(
    from_module: str = typer.Option(..., "--from", help="Importer module"),
    to_module: str = typer.Option(..., "--to", help="Imported module"),
    path: Path = typer.Option(Path("."), "--path"),
) -> None:
    """Exit 1 if adding importer→imported would enlarge a runtime cycle."""
    result = _graph(path.resolve())
    check = would_create_cycle(result, importer=from_module, imported=to_module)
    console.print(check.detail)
    if check.would_create_or_enlarge:
        raise typer.Exit(code=1)
