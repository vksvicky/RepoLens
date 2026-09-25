"""Ingest precomputed import edges (future Sonargraph / SCIP adapters)."""

from __future__ import annotations

import json
from pathlib import Path

from repolens.config import GraphConfig
from repolens.graph.build import _passes_gate
from repolens.graph.cycles import cyclicity, strongly_connected_components
from repolens.graph.types import (
    CycleGroup,
    EdgeKind,
    GraphResult,
    GraphStatus,
    ImportEdge,
    ImportScope,
)


def load_precomputed_edges(path: Path, *, config: GraphConfig | None = None) -> GraphResult:
    """Load a JSON edge list and compute SCCs without grimp.

    Each list item is an object with required ``importer`` and ``imported`` strings,
    plus optional ``kind``, ``scope``, and ``line`` fields matching :class:`ImportEdge`.
    """
    cfg = config or GraphConfig()
    path = path.resolve()
    gaps: list[str] = []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return GraphResult(
            status=GraphStatus.FAILED,
            durability_gaps=[f"graph.analysis_failed: {path} not found"],
        )
    except OSError as exc:
        return GraphResult(
            status=GraphStatus.FAILED,
            durability_gaps=[f"graph.analysis_failed: cannot read {path}: {exc}"],
        )
    except json.JSONDecodeError as exc:
        return GraphResult(
            status=GraphStatus.FAILED,
            durability_gaps=[f"graph.analysis_failed: invalid JSON in {path}: {exc}"],
        )

    if not isinstance(payload, list):
        return GraphResult(
            status=GraphStatus.FAILED,
            durability_gaps=["graph.analysis_failed: edge list must be a JSON array"],
        )

    edges: list[ImportEdge] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            gaps.append(f"graph.analysis_failed: edge[{index}] must be an object")
            continue
        try:
            edges.append(_edge_from_dict(item))
        except ValueError as exc:
            gaps.append(f"graph.analysis_failed: edge[{index}]: {exc}")

    gated_edges = [e for e in edges if _passes_gate(e, cfg)]
    edge_pairs = [(e.importer, e.imported) for e in gated_edges]
    all_sccs = strongly_connected_components(edge_pairs)
    cyclic_sccs = [s for s in all_sccs if len(s) >= 2]

    cycles: list[CycleGroup] = []
    for scc in cyclic_sccs:
        scc_set = set(scc)
        representative: ImportEdge | None = None
        for edge in gated_edges:
            if edge.importer in scc_set and edge.imported in scc_set:
                representative = edge
                break
        cycles.append(CycleGroup(modules=scc, representative_edge=representative))

    modules: set[str] = set()
    for edge in edges:
        modules.add(edge.importer)
        modules.add(edge.imported)

    status = GraphStatus.PARTIAL if gaps else GraphStatus.OK
    return GraphResult(
        status=status,
        edges=edges,
        gated_edges=gated_edges,
        cycles=cycles,
        cyclicity=cyclicity(cyclic_sccs),
        module_count=len(modules),
        durability_gaps=gaps,
    )


def _edge_from_dict(item: dict[str, object]) -> ImportEdge:
    importer = item.get("importer")
    imported = item.get("imported")
    if not isinstance(importer, str) or not importer.strip():
        raise ValueError("importer must be a non-empty string")
    if not isinstance(imported, str) or not imported.strip():
        raise ValueError("imported must be a non-empty string")

    kind = _parse_kind(item.get("kind"))
    scope = _parse_scope(item.get("scope"))
    line_raw = item.get("line")
    line: int | None = None
    if line_raw is not None:
        if not isinstance(line_raw, int):
            raise ValueError("line must be an integer")
        line = line_raw

    line_contents = item.get("line_contents")
    if line_contents is not None and not isinstance(line_contents, str):
        raise ValueError("line_contents must be a string")

    return ImportEdge(
        importer=importer,
        imported=imported,
        kind=kind,
        scope=scope,
        line=line,
        line_contents=line_contents if isinstance(line_contents, str) else None,
    )


def _parse_kind(raw: object) -> EdgeKind:
    if raw is None:
        return EdgeKind.RUNTIME
    if isinstance(raw, str):
        try:
            return EdgeKind(raw)
        except ValueError as exc:
            raise ValueError(f"unknown kind {raw!r}") from exc
    raise ValueError("kind must be a string")


def _parse_scope(raw: object) -> ImportScope:
    if raw is None:
        return ImportScope.MODULE
    if isinstance(raw, str):
        try:
            return ImportScope(raw)
        except ValueError as exc:
            raise ValueError(f"unknown scope {raw!r}") from exc
    raise ValueError("scope must be a string")
