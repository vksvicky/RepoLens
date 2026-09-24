"""Cyclicity baseline CLI (G2): ``baseline set`` / ``show``."""

from __future__ import annotations

from pathlib import Path

import typer

from repolens import __version__
from repolens.cli.app import baseline_app, console
from repolens.config import GraphConfig, load_config
from repolens.graph import analyse_python_graph
from repolens.graph.baseline import (
    DEFAULT_BASELINE_PATH,
    baseline_from_graph,
    load_baseline,
    write_baseline,
)
from repolens.graph.types import GraphStatus


def _resolve_baseline_path(
    root: Path,
    *,
    out: Path | None,
    baseline_path: str,
) -> Path:
    """Resolve write/read path: ``--out`` → config → default (relative to root)."""
    if out is not None:
        return out.resolve() if out.is_absolute() else (root / out).resolve()
    rel = baseline_path.strip() or DEFAULT_BASELINE_PATH
    candidate = Path(rel)
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _graph_config_for_root(root: Path) -> GraphConfig:
    cfg = load_config(root)
    return cfg.graph


@baseline_app.command("set")
def baseline_set(
    path: Path = typer.Option(Path("."), "--path", help="Project root to analyse"),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Baseline JSON path (default: config baseline_path or .repolens/baseline.json)",
    ),
) -> None:
    """Analyse the Python import graph and write a cyclicity baseline."""
    root = path.resolve()
    graph_cfg = _graph_config_for_root(root)
    target = _resolve_baseline_path(
        root, out=out, baseline_path=graph_cfg.baseline_path
    )
    result = analyse_python_graph(root, config=graph_cfg)
    if result.status is GraphStatus.FAILED:
        for gap in result.durability_gaps:
            console.print(f"[red]{gap}[/red]")
        console.print("[red]Graph analysis failed; baseline not written.[/red]")
        raise typer.Exit(code=3)
    if result.status is GraphStatus.SKIPPED:
        for gap in result.durability_gaps:
            console.print(f"[red]{gap}[/red]")
        console.print(
            "[red]Graph analysis was skipped (e.g. graph disabled); "
            "baseline not written.[/red]"
        )
        raise typer.Exit(code=3)
    doc = baseline_from_graph(result, config=graph_cfg, version=__version__)
    write_baseline(target, doc)
    fps = doc["graph"]["fingerprints"]
    console.print(f"[green]Wrote[/green] baseline → {target}")
    console.print(f"Cyclicity: {doc['graph']['cyclicity']}")
    console.print(f"Fingerprints: {len(fps)}")


@baseline_app.command("show")
def baseline_show(
    path: Path = typer.Option(Path("."), "--path", help="Project root"),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Baseline JSON path (default: config baseline_path or .repolens/baseline.json)",
    ),
) -> None:
    """Print cyclicity, fingerprint count, and baseline path."""
    root = path.resolve()
    graph_cfg = _graph_config_for_root(root)
    target = _resolve_baseline_path(
        root, out=out, baseline_path=graph_cfg.baseline_path
    )
    if not target.is_file():
        console.print(f"[red]No baseline found at[/red] {target}")
        console.print("Run [cyan]repolens baseline set[/cyan] to create one.")
        raise typer.Exit(code=2)
    doc = load_baseline(target)
    graph = doc.get("graph") or {}
    cyclicity = graph.get("cyclicity", "?")
    fps = graph.get("fingerprints") or []
    console.print(f"Baseline: {target}")
    console.print(f"Cyclicity: {cyclicity}")
    console.print(f"Fingerprints: {len(fps)}")
