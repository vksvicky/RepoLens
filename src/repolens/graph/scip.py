"""Ingest Sourcegraph SCIP Index JSON (no protobuf)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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

_IMPORT_ROLE = 1


def _documents(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("documents") or payload.get("Documents") or []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _doc_path(document: dict[str, Any]) -> str:
    return str(
        document.get("relative_path")
        or document.get("relativePath")
        or document.get("relative-path")
        or ""
    ).replace("\\", "/")


def _occurrences(document: dict[str, Any]) -> list[dict[str, Any]]:
    raw = document.get("occurrences") or document.get("Occurrences") or []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _roles(occ: dict[str, Any]) -> int:
    raw = occ.get("symbol_roles", occ.get("symbolRoles", 0))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _line(occ: dict[str, Any]) -> int | None:
    rng = occ.get("range") or occ.get("Range")
    if not isinstance(rng, list) or not rng:
        return None
    try:
        start = int(rng[0])
    except (TypeError, ValueError):
        return None
    return start + 1


def _result_from_edges(
    edges: list[ImportEdge], *, gaps: list[str], config: GraphConfig
) -> GraphResult:
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
    status = GraphStatus.PARTIAL if gaps else GraphStatus.OK
    if not edges and gaps:
        status = GraphStatus.FAILED
    return GraphResult(
        status=status,
        edges=edges,
        gated_edges=gated,
        cycles=cycles,
        cyclicity=cyclicity(cyclic),
        module_count=len(modules),
        durability_gaps=gaps,
    )


def load_scip_json(path: Path, *, config: GraphConfig | None = None) -> GraphResult:
    """Load a SCIP Index JSON object into import edges."""
    cfg = config or GraphConfig()
    path = path.resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return GraphResult(
            status=GraphStatus.FAILED,
            durability_gaps=[f"graph.analysis_failed: {path} not found"],
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return GraphResult(
            status=GraphStatus.FAILED,
            durability_gaps=[f"graph.analysis_failed: invalid SCIP JSON in {path}: {exc}"],
        )
    if not isinstance(payload, dict):
        return GraphResult(
            status=GraphStatus.FAILED,
            durability_gaps=["graph.analysis_failed: SCIP JSON must be an object"],
        )
    edges: list[ImportEdge] = []
    for document in _documents(payload):
        importer = _doc_path(document)
        if not importer:
            continue
        for occ in _occurrences(document):
            if _roles(occ) & _IMPORT_ROLE == 0:
                continue
            symbol = str(occ.get("symbol") or occ.get("Symbol") or "").strip()
            if not symbol:
                continue
            edges.append(
                ImportEdge(
                    importer=importer,
                    imported=symbol,
                    kind=EdgeKind.RUNTIME,
                    scope=ImportScope.MODULE,
                    line=_line(occ),
                )
            )
    return _result_from_edges(edges, gaps=[], config=cfg)
