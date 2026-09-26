"""Graph reachability and proposed-edge cycle checks (G3 tooling core)."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from repolens.graph.cycles import strongly_connected_components
from repolens.graph.types import GraphResult, ImportEdge


@dataclass(frozen=True)
class CycleCheckResult:
    would_create_or_enlarge: bool
    cycle_modules: tuple[str, ...]
    detail: str


def direct_dependencies(result: GraphResult, module: str) -> list[str]:
    return sorted(
        {
            e.imported
            for e in result.gated_edges
            if e.importer == module
        }
    )


def direct_dependents(result: GraphResult, module: str) -> list[str]:
    return sorted(
        {
            e.importer
            for e in result.gated_edges
            if e.imported == module
        }
    )


def reachable_dependencies(result: GraphResult, module: str) -> list[str]:
    return _bfs(result, start=module, forward=True)


def reachable_dependents(result: GraphResult, module: str) -> list[str]:
    return _bfs(result, start=module, forward=False)


def would_create_cycle(
    result: GraphResult, *, importer: str, imported: str
) -> CycleCheckResult:
    """True when adding importer→imported enlarges runtime cycle debt."""
    if importer == imported:
        return CycleCheckResult(
            would_create_or_enlarge=True,
            cycle_modules=(importer,),
            detail="Self-import always forms a trivial cycle.",
        )
    pairs = [(e.importer, e.imported) for e in result.gated_edges]
    before = {
        frozenset(s)
        for s in strongly_connected_components(pairs)
        if len(s) >= 2
    }
    after_pairs = pairs + [(importer, imported)]
    after_sccs = [
        s for s in strongly_connected_components(after_pairs) if len(s) >= 2
    ]
    after = {frozenset(s) for s in after_sccs}
    if after == before:
        # Still check if the two modules already share an SCC (edge redundant).
        shared = _shared_cycle(after_sccs, importer, imported)
        if shared:
            return CycleCheckResult(
                False,
                shared,
                "Edge already inside an existing runtime cycle (no enlargement).",
            )
        return CycleCheckResult(
            False,
            (),
            "Proposed edge does not create or enlarge a runtime cycle.",
        )
    # Find the SCC containing both after the edge.
    for scc in after_sccs:
        if importer in scc and imported in scc:
            return CycleCheckResult(
                True,
                scc,
                f"Proposed edge would create/enlarge runtime cycle among {len(scc)} modules.",
            )
    # Cyclicity changed but pair not co-located — still flag enlargement.
    enlarged = tuple(sorted(max(after_sccs, key=len))) if after_sccs else ()
    return CycleCheckResult(
        True,
        enlarged,
        "Proposed edge changes runtime strongly-connected structure.",
    )


def check_dependency(
    result: GraphResult, *, importer: str, imported: str
) -> CycleCheckResult:
    """Alias used by MCP: reject when proposed edge creates/worsens a runtime cycle."""
    return would_create_cycle(result, importer=importer, imported=imported)


def _shared_cycle(
    sccs: list[tuple[str, ...]], a: str, b: str
) -> tuple[str, ...]:
    for scc in sccs:
        if a in scc and b in scc:
            return scc
    return ()


def _bfs(result: GraphResult, *, start: str, forward: bool) -> list[str]:
    adj: dict[str, set[str]] = defaultdict(set)
    for edge in result.gated_edges:
        if forward:
            adj[edge.importer].add(edge.imported)
        else:
            adj[edge.imported].add(edge.importer)
    seen: set[str] = set()
    q: deque[str] = deque([start])
    while q:
        node = q.popleft()
        for nxt in sorted(adj.get(node, ())):
            if nxt in seen or nxt == start:
                continue
            seen.add(nxt)
            q.append(nxt)
    return sorted(seen)


def edges_between(result: GraphResult, a: str, b: str) -> list[ImportEdge]:
    return [
        e
        for e in result.gated_edges
        if (e.importer == a and e.imported == b)
        or (e.importer == b and e.imported == a)
    ]
