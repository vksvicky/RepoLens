"""Convert import-graph SCCs into canonical Issue rows."""

from __future__ import annotations

from repolens.graph.types import CycleGroup, GraphResult, ImportEdge
from repolens.schema import Issue, Severity


def cycles_to_issues(result: GraphResult, *, critical_scc_size: int = 8) -> list[Issue]:
    """Emit exactly one finding per runtime SCC (size ≥ 2) in ``result.cycles``."""
    issues: list[Issue] = []
    for group in result.cycles:
        n = len(group.modules)
        if n < 2:
            continue
        severity = (
            Severity.CRITICAL if n >= critical_scc_size else Severity.HIGH
        )
        issues.append(_cycle_group_to_issue(group, severity=severity))
    return issues


def _cycle_group_to_issue(group: CycleGroup, *, severity: Severity) -> Issue:
    n = len(group.modules)
    file_path, line = _location_for_group(group)
    code_example = _code_example(group)
    members = ", ".join(group.modules)
    return Issue(
        severity=severity,
        priority="P3",
        category="arch.import_cycle",
        file=file_path,
        line=line,
        title=_title_for_group(group.modules),
        explanation=(
            f"The analysed import graph contains a strongly connected group of {n} "
            f"modules with mutual runtime dependencies: {members}. "
            "Every module in the group can reach every other via import edges."
        ),
        impact=(
            "Mutual imports make initialisation order unpredictable, hide layering "
            "violations, and increase the cost of testing and refactors."
        ),
        recommendedFix=(
            "Break the cycle by moving shared contracts to a neutral module or "
            "introducing dependency inversion so members depend on abstractions "
            "rather than on each other."
        ),
        codeExample=code_example,
        fixTiming="before launch",
        source="graph",
        clusteredCount=n,
    )


def _title_for_group(modules: tuple[str, ...]) -> str:
    n = len(modules)
    if n <= 4:
        preview = ", ".join(modules)
    else:
        preview = ", ".join(modules[:3]) + ", …"
    return f"Cyclic dependency group: {n} modules ({preview})"


def _location_for_group(group: CycleGroup) -> tuple[str, int]:
    edge = group.representative_edge
    if edge is not None:
        line = edge.line if edge.line is not None and edge.line >= 1 else 1
        return _module_to_file(edge.importer), line
    return _module_to_file(group.modules[0]), 1


def _code_example(group: CycleGroup) -> str:
    edge = group.representative_edge
    if edge is not None:
        if edge.line_contents and edge.line_contents.strip():
            return edge.line_contents.strip()
        return _sketch_from_edge(edge)
    if len(group.modules) >= 2:
        a, b = group.modules[0], group.modules[1]
        return f"# {a} ↔ {b}\n# mutual runtime imports in this SCC"
    return f"# {group.modules[0]}\n# self-referential import group"


def _sketch_from_edge(edge: ImportEdge) -> str:
    imported_leaf = edge.imported.rsplit(".", 1)[-1]
    return f"# {edge.importer} → {edge.imported}\nimport {imported_leaf}"


def _module_to_file(module: str) -> str:
    return module.replace(".", "/") + ".py"
