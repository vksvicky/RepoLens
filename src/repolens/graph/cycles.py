"""Strongly connected components (Tarjan) and cyclicity metric."""

from __future__ import annotations

from collections.abc import Sequence


def strongly_connected_components(
    edges: Sequence[tuple[str, str]],
) -> list[tuple[str, ...]]:
    """Return all SCCs as sorted module-name tuples (stable ordering)."""
    adj: dict[str, list[str]] = {}
    nodes: set[str] = set()
    for u, v in edges:
        nodes.add(u)
        nodes.add(v)
        adj.setdefault(u, []).append(v)
    for n in nodes:
        adj.setdefault(n, [])

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    raw: list[list[str]] = []

    def strongconnect(v: str) -> None:
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in adj[v]:
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])

        if lowlink[v] == indices[v]:
            scc: list[str] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.append(w)
                if w == v:
                    break
            raw.append(scc)

    for v in sorted(nodes):
        if v not in indices:
            strongconnect(v)

    out = [tuple(sorted(scc)) for scc in raw]
    out.sort()
    return out


def cyclicity(sccs: Sequence[tuple[str, ...]]) -> int:
    """Sum of n² over SCCs with n ≥ 2 (cycle debt for G1 reporting)."""
    return sum(len(s) ** 2 for s in sccs if len(s) >= 2)
