"""Merge multiple GraphResult edge lists and recompute SCCs once."""

from __future__ import annotations

from repolens.config import GraphConfig
from repolens.graph.build import _passes_gate
from repolens.graph.cycles import cyclicity, strongly_connected_components
from repolens.graph.types import (
    CycleGroup,
    GraphResult,
    GraphStatus,
    ImportEdge,
)


def merge_graph_results(
    parts: list[GraphResult], *, config: GraphConfig
) -> GraphResult:
    edges: list[ImportEdge] = []
    seen: set[tuple[str, str, int]] = set()
    gaps: list[str] = []
    packages: list[str] = []
    for part in parts:
        packages.extend(part.packages)
        gaps.extend(part.durability_gaps)
        for edge in part.edges:
            key = (edge.importer, edge.imported, edge.line or 0)
            if key in seen:
                continue
            seen.add(key)
            edges.append(edge)
    if not parts:
        return GraphResult(status=GraphStatus.SKIPPED, durability_gaps=["graph: empty"])

    gated = [e for e in edges if _passes_gate(e, config)]
    pairs = [(e.importer, e.imported) for e in gated]
    sccs = strongly_connected_components(pairs)
    cyclic = [s for s in sccs if len(s) >= 2]
    cycles: list[CycleGroup] = []
    for scc in cyclic:
        scc_set = set(scc)
        representative = next(
            (
                edge
                for edge in gated
                if edge.importer in scc_set and edge.imported in scc_set
            ),
            None,
        )
        cycles.append(CycleGroup(modules=scc, representative_edge=representative))
    modules: set[str] = set()
    for edge in edges:
        modules.add(edge.importer)
        modules.add(edge.imported)

    produced = bool(edges)
    statuses = {part.status for part in parts}
    any_failed = any(part.status is GraphStatus.FAILED for part in parts)
    if not produced:
        if any_failed:
            status = GraphStatus.FAILED
        elif statuses <= {GraphStatus.SKIPPED}:
            status = GraphStatus.SKIPPED
        elif GraphStatus.OK in statuses or GraphStatus.PARTIAL in statuses:
            status = GraphStatus.PARTIAL if gaps else GraphStatus.OK
        elif gaps:
            status = GraphStatus.PARTIAL
        else:
            status = GraphStatus.SKIPPED
    elif gaps or any_failed or GraphStatus.PARTIAL in statuses:
        status = GraphStatus.PARTIAL
    else:
        status = GraphStatus.OK
    return GraphResult(
        status=status,
        packages=list(dict.fromkeys(packages)),
        edges=edges,
        gated_edges=gated,
        cycles=cycles,
        cyclicity=cyclicity(cyclic),
        module_count=len(modules),
        durability_gaps=gaps,
    )
