"""``repolens graph`` — query the Python import graph (C2)."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from repolens.architecture.fas import (
    candidate_feedback_arc_sets,
    metrics_without_edges,
    parse_omit_edge_token,
)
from repolens.cli.app import app, console
from repolens.config import load_config
from repolens.graph import analyse_repo_graph
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
    result = analyse_repo_graph(root, config=cfg.graph)
    if result.status == GraphStatus.FAILED:
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
    cycles_out = []
    for c in result.cycles:
        scc = set(c.modules)
        edges = [
            {
                "importer": e.importer,
                "imported": e.imported,
                "line": e.line,
                "kind": str(e.kind),
            }
            for e in result.gated_edges
            if e.importer in scc and e.imported in scc
        ]
        cycles_out.append({"modules": list(c.modules), "edges": edges})
    payload = {
        "cyclicity": result.cyclicity,
        "cycleCount": len(result.cycles),
        "cycles": cycles_out,
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


@graph_app.command("breakup")
def graph_breakup(
    path: Path = typer.Option(Path("."), "--path"),
    fmt: str = typer.Option("json", "--format", help="json"),
    omit_edge: list[str] | None = typer.Option(
        None,
        "--omit-edge",
        help="Preview without this import (importer:imported). Repeatable. Does not edit files.",
    ),
) -> None:
    """Candidate cycle cuts, or cyclicity after omitting edges. JSON on stdout."""
    if fmt.strip().lower() != "json":
        console.print("[red]--format must be json[/red]")
        raise typer.Exit(code=2)
    omitted: list[tuple[str, str]] = []
    for token in omit_edge or []:
        try:
            omitted.append(parse_omit_edge_token(token))
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=2) from exc
    result = _graph(path.resolve())
    cyclicity_now, sccs = metrics_without_edges(result, omitted)
    candidates = []
    if not omitted:
        for cand in candidate_feedback_arc_sets(result):
            candidates.append(
                {
                    "label": cand.label,
                    "totalWeight": cand.total_weight,
                    "edges": [
                        {
                            "importer": e.importer,
                            "imported": e.imported,
                            "weight": e.weight,
                            "line": e.line,
                        }
                        for e in cand.edges
                    ],
                }
            )
    payload = {
        "cyclicity": cyclicity_now,
        "cycleCount": len(sccs),
        "cycles": [{"modules": list(s)} for s in sccs],
        "candidates": candidates,
        "omitted": [{"importer": a, "imported": b} for a, b in omitted],
        "note": "Preview only — no files were edited.",
    }
    typer.echo(json.dumps(payload, indent=2))


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
