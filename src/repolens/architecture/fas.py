"""Weighted feedback-arc-set candidates for cycle remediation (G4).

FAS verifies that a cut breaks every cycle. Architecture (layer direction /
domain rules) chooses which valid candidate set to apply — never present
minimum weight alone as the refactoring answer.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from repolens.graph.cycles import cyclicity, strongly_connected_components
from repolens.graph.types import CycleGroup, GraphResult, ImportEdge


@dataclass(frozen=True)
class WeightedEdge:
    importer: str
    imported: str
    weight: int
    line: int | None = None
    line_contents: str | None = None


@dataclass(frozen=True)
class FasCandidate:
    """One cycle-breaking cut option (not gospel)."""

    edges: tuple[WeightedEdge, ...]
    total_weight: int
    label: str


def edge_weights(edges: Sequence[ImportEdge]) -> dict[tuple[str, str], WeightedEdge]:
    """Aggregate import edges; weight = number of observed imports (min 1)."""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    meta: dict[tuple[str, str], ImportEdge] = {}
    for edge in edges:
        key = (edge.importer, edge.imported)
        counts[key] += 1
        meta.setdefault(key, edge)
    out: dict[tuple[str, str], WeightedEdge] = {}
    for key, count in counts.items():
        sample = meta[key]
        out[key] = WeightedEdge(
            importer=key[0],
            imported=key[1],
            weight=max(1, count),
            line=sample.line,
            line_contents=sample.line_contents,
        )
    return out


def violation_subgraph_edges(
    result: GraphResult, *, cycles: Sequence[CycleGroup] | None = None
) -> list[ImportEdge]:
    """Edges that participate in at least one gated SCC (size ≥ 2)."""
    groups = list(cycles) if cycles is not None else result.cycles
    members: set[str] = set()
    for group in groups:
        if len(group.modules) >= 2:
            members.update(group.modules)
    if not members:
        return []
    return [
        e
        for e in result.gated_edges
        if e.importer in members and e.imported in members
    ]


def candidate_feedback_arc_sets(
    result: GraphResult,
    *,
    max_candidates: int = 3,
) -> list[FasCandidate]:
    """Return up to *max_candidates* cycle-breaking cuts (lightest-first greedy + alts)."""
    sub = violation_subgraph_edges(result)
    if not sub:
        return []
    weights = edge_weights(sub)
    pairs = [(e.importer, e.imported) for e in sub]
    sccs = [s for s in strongly_connected_components(pairs) if len(s) >= 2]
    if not sccs:
        return []

    # Rank unique edges by weight ascending (prefer light cuts).
    ranked = sorted(weights.values(), key=lambda w: (w.weight, w.importer, w.imported))
    candidates: list[FasCandidate] = []

    # Candidate 0: greedy lightest-first until acyclic.
    greedy = _greedy_cut(pairs, ranked)
    if greedy:
        candidates.append(
            FasCandidate(
                edges=tuple(greedy),
                total_weight=sum(e.weight for e in greedy),
                label="greedy_lightest",
            )
        )

    # Alternatives: force-start with each of the next-lightest edges.
    for starter in ranked[: max_candidates + 2]:
        if len(candidates) >= max_candidates:
            break
        alt_ranked = [starter] + [e for e in ranked if e != starter]
        cut = _greedy_cut(pairs, alt_ranked)
        if not cut:
            continue
        key = tuple(sorted((e.importer, e.imported) for e in cut))
        if any(
            tuple(sorted((e.importer, e.imported) for e in c.edges)) == key
            for c in candidates
        ):
            continue
        candidates.append(
            FasCandidate(
                edges=tuple(cut),
                total_weight=sum(e.weight for e in cut),
                label=f"alt_start_{starter.importer}->{starter.imported}",
            )
        )

    return candidates[:max_candidates]


def _greedy_cut(
    pairs: list[tuple[str, str]],
    ranked: Sequence[WeightedEdge],
) -> list[WeightedEdge]:
    remaining = set(pairs)
    cut: list[WeightedEdge] = []
    while True:
        sccs = [s for s in strongly_connected_components(list(remaining)) if len(s) >= 2]
        if not sccs or cyclicity(sccs) == 0:
            break
        members = {m for s in sccs for m in s}
        progress = False
        for edge in ranked:
            key = (edge.importer, edge.imported)
            if key not in remaining:
                continue
            if edge.importer not in members or edge.imported not in members:
                continue
            remaining.remove(key)
            cut.append(edge)
            progress = True
            break
        if not progress:
            break
    return cut
