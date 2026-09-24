from pathlib import Path

from repolens.graph import analyse_python_graph
from repolens.config import GraphConfig
from repolens.graph.types import GraphStatus, ImportScope

FIXTURES = Path(__file__).parent / "fixtures"


def test_detects_runtime_cycle():
    root = FIXTURES / "graph_cycle_pkg"
    result = analyse_python_graph(root)
    assert result.status in {GraphStatus.OK, GraphStatus.PARTIAL}
    assert len(result.cycles) == 1
    assert result.cyclicity >= 4
    modules = set(result.cycles[0].modules)
    assert modules == {"packcycle.a", "packcycle.b"}


def test_excludes_function_local_by_default():
    root = FIXTURES / "graph_lazy_pkg"
    result = analyse_python_graph(root)
    assert result.cycles == []


def test_includes_function_local_when_configured():
    root = FIXTURES / "graph_lazy_pkg"
    result = analyse_python_graph(
        root,
        config=GraphConfig(local_imports="include"),
    )
    assert len(result.cycles) == 1


def test_type_checking_ignored():
    root = FIXTURES / "graph_typecheck_pkg"
    result = analyse_python_graph(root)
    assert result.cycles == []


def test_lazy_edge_tagged_function_local():
    root = FIXTURES / "graph_lazy_pkg"
    result = analyse_python_graph(root)
    lazy_edges = [
        e
        for e in result.edges
        if e.importer == "packlazy.a" and e.imported == "packlazy.b"
    ]
    assert len(lazy_edges) == 1
    assert lazy_edges[0].scope is ImportScope.FUNCTION_LOCAL


def test_disabled_skips_analysis():
    root = FIXTURES / "graph_cycle_pkg"
    result = analyse_python_graph(root, config=GraphConfig(enabled=False))
    assert result.status is GraphStatus.SKIPPED
    assert "graph: disabled" in result.durability_gaps[0]


def test_cycle_has_representative_edge():
    root = FIXTURES / "graph_cycle_pkg"
    result = analyse_python_graph(root)
    rep = result.cycles[0].representative_edge
    assert rep is not None
    assert rep.importer in result.cycles[0].modules
    assert rep.imported in result.cycles[0].modules


def test_no_packages_fails(tmp_path):
    result = analyse_python_graph(tmp_path)
    assert result.status is GraphStatus.FAILED
    assert any("no packages discovered" in g for g in result.durability_gaps)


def test_syntax_error_durability_gap(tmp_path):
    pkg = tmp_path / "badpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("def (\n")
    (pkg / "b.py").write_text("import badpkg.a\n")
    result = analyse_python_graph(tmp_path)
    assert result.status is GraphStatus.FAILED
    assert any("graph.analysis_failed" in g for g in result.durability_gaps)


def test_grimp_failure_returns_failed(monkeypatch, tmp_path):
    pkg = tmp_path / "okpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("x = 1\n")

    import grimp

    def boom(*args, **kwargs):
        raise RuntimeError("grimp unavailable")

    monkeypatch.setattr(grimp, "build_graph", boom)
    result = analyse_python_graph(tmp_path)
    assert result.status is GraphStatus.FAILED
    assert any("grimp unavailable" in g for g in result.durability_gaps)
