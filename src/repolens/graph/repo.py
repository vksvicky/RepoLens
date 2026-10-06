"""Merged repo graph: Python grimp + optional tree-sitter + SCIP/JSON extras."""

from __future__ import annotations

from pathlib import Path

from repolens.config import GraphConfig
from repolens.graph.adapters import load_precomputed_edges
from repolens.graph.build import analyse_python_graph
from repolens.graph.merge import merge_graph_results
from repolens.graph.scip import load_scip_json
from repolens.graph.tree_sitter_imports import collect_tree_sitter_edges
from repolens.graph.types import GraphResult, GraphStatus


def _safe_under_root(root: Path, relative: str) -> Path | None:
    if not relative or not str(relative).strip():
        return None
    candidate = Path(relative)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def analyse_repo_graph(root: Path, *, config: GraphConfig | None = None) -> GraphResult:
    """Build the union graph used by check, baseline, review, and MCP."""
    cfg = config or GraphConfig()
    root = root.resolve()
    parts: list[GraphResult] = []
    python = analyse_python_graph(root, config=cfg)
    if python.status is GraphStatus.FAILED and not python.edges:
        parts.append(
            GraphResult(
                status=GraphStatus.SKIPPED,
                durability_gaps=list(python.durability_gaps),
                packages=list(python.packages),
            )
        )
    else:
        parts.append(python)

    ts = collect_tree_sitter_edges(root, config=cfg)
    if ts.status is not GraphStatus.SKIPPED:
        if ts.status is GraphStatus.FAILED and not ts.edges:
            parts.append(ts)
        else:
            parts.append(ts)

    extra = _safe_under_root(root, cfg.extra_edges)
    if extra is not None:
        parts.append(load_precomputed_edges(extra, config=cfg))
    elif str(cfg.extra_edges).strip():
        parts.append(
            GraphResult(
                status=GraphStatus.FAILED,
                durability_gaps=[
                    f"graph.analysis_failed: extra_edges escapes project root: {cfg.extra_edges}"
                ],
            )
        )
    scip = _safe_under_root(root, cfg.scip)
    if scip is not None:
        parts.append(load_scip_json(scip, config=cfg))
    elif str(cfg.scip).strip():
        parts.append(
            GraphResult(
                status=GraphStatus.FAILED,
                durability_gaps=[
                    f"graph.analysis_failed: scip path escapes project root: {cfg.scip}"
                ],
            )
        )
    return merge_graph_results(parts, config=cfg)
