"""``repolens check architecture`` — DSL verify + FAS candidates (G4)."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from repolens.architecture import (
    ArchitectureLoadError,
    boundary_violations_to_issues,
    candidate_feedback_arc_sets,
    discover_architecture_path,
    load_architecture,
    remediation_context,
    verify_boundaries,
)
from repolens.cli.app import check_app, console
from repolens.config import load_config
from repolens.graph import analyse_python_graph
from repolens.graph.types import GraphStatus


@check_app.command("architecture")
def check_architecture(
    path: Path = typer.Option(Path("."), "--path", help="Project root"),
    architecture: Path | None = typer.Option(
        None,
        "--architecture",
        help="Path to repolens.yaml / architecture.json (default: auto-discover)",
    ),
    json_out: bool = typer.Option(
        False,
        "--json",
        help="Emit remediation context JSON (subgraph + FAS candidates)",
    ),
) -> None:
    """Verify architecture DSL boundaries against the import graph."""
    root = path.expanduser().resolve()
    cfg = load_config(root)
    try:
        arch_path = discover_architecture_path(root, explicit=architecture)
    except ArchitectureLoadError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    if arch_path is None:
        console.print(
            "[red]No architecture file found.[/red] Expected one of: "
            "repolens.yaml, .repolens/architecture.yaml, architecture.json"
        )
        raise typer.Exit(code=2)

    try:
        doc = load_architecture(arch_path)
    except ArchitectureLoadError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    result = analyse_python_graph(root, config=cfg.graph)
    if result.status is GraphStatus.FAILED:
        for gap in result.durability_gaps:
            console.print(f"[red]{gap}[/red]")
        raise typer.Exit(code=3)
    if result.status is GraphStatus.SKIPPED:
        console.print("[red]Graph analysis skipped; cannot verify architecture.[/red]")
        raise typer.Exit(code=3)

    violations = verify_boundaries(result, doc)
    candidates = candidate_feedback_arc_sets(result)
    ctx = remediation_context(result, violations=violations)

    if json_out:
        console.print(json.dumps(ctx, indent=2, sort_keys=True))
    else:
        console.print(f"Architecture: {arch_path}")
        console.print(f"Boundaries: {len(doc.boundaries)}")
        console.print(f"Cyclicity: {result.cyclicity}")
        console.print(f"Boundary violations: {len(violations)}")
        for v in violations:
            loc = f"{v.importer}:{v.edge.line or '?'}"
            console.print(
                f"  [red]FAIL[/red] {loc}  {v.from_boundary} → {v.to_boundary}: {v.reason}"
            )
        if candidates:
            console.print(f"FAS candidates: {len(candidates)} (not auto-applied)")
            for c in candidates:
                edges = ", ".join(
                    f"{e.importer}→{e.imported}(w={e.weight})" for e in c.edges
                )
                console.print(
                    f"  [cyan]{c.label}[/cyan] weight={c.total_weight}: {edges}"
                )
        issues = boundary_violations_to_issues(violations)
        if issues:
            console.print(f"Issues emitted: {len(issues)} (arch.boundary_violation)")

    if violations:
        raise typer.Exit(code=1)
    console.print("[green]Architecture boundaries OK[/green]")
