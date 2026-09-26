from repolens.graph.findings import cycles_to_issues
from repolens.graph.types import (
    CycleGroup,
    EdgeKind,
    GraphResult,
    GraphStatus,
    ImportEdge,
    ImportScope,
)
from repolens.schema import Severity


def test_one_finding_per_scc():
    modules = tuple(f"m{i}" for i in range(6))
    edge = ImportEdge(
        "m5",
        "m0",
        EdgeKind.RUNTIME,
        ImportScope.MODULE,
        line=1,
        line_contents="import m0",
    )
    result = GraphResult(
        status=GraphStatus.OK,
        cycles=[CycleGroup(modules=modules, representative_edge=edge)],
        cyclicity=36,
    )
    issues = cycles_to_issues(result)
    assert len(issues) == 1
    assert issues[0].source == "graph"
    assert issues[0].severity == Severity.HIGH
    assert issues[0].category == "arch.import_cycle"
    assert issues[0].priority == "P3"
    assert "6 modules" in issues[0].title
    assert issues[0].impact.strip()
    assert issues[0].codeExample.strip()


def test_large_scc_critical():
    modules = tuple(f"m{i}" for i in range(8))
    result = GraphResult(
        status=GraphStatus.OK,
        cycles=[CycleGroup(modules=modules)],
        cyclicity=64,
    )
    assert cycles_to_issues(result)[0].severity == Severity.CRITICAL
