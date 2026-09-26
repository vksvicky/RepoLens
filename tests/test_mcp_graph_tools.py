"""Graph query helpers and MCP tool functions (G3)."""

from __future__ import annotations

from pathlib import Path

from repolens.architecture import ArchitectureDoc, Boundary
from repolens.graph import analyse_python_graph
from repolens.graph.query import (
    check_dependency,
    direct_dependencies,
    would_create_cycle,
)
from repolens.mcp.server import (
    tool_check_dependency,
    tool_get_legal_imports,
    tool_query_dependencies,
)

FIXTURES = Path(__file__).parent / "fixtures"
CYCLE_PKG = FIXTURES / "graph_cycle_pkg"


def test_direct_dependencies_cycle_fixture() -> None:
    result = analyse_python_graph(CYCLE_PKG)
    deps = direct_dependencies(result, "packcycle.a")
    assert "packcycle.b" in deps


def test_would_create_cycle_on_existing_edge() -> None:
    result = analyse_python_graph(CYCLE_PKG)
    # Edge already in cycle — should not report enlargement when already present...
    # Adding a→b again: already in SCC, would_create check adds duplicate edge.
    check = would_create_cycle(result, importer="packcycle.a", imported="packcycle.b")
    # Duplicate edge inside existing cycle → not an enlargement
    assert check.would_create_or_enlarge is False


def test_check_dependency_self_import() -> None:
    result = analyse_python_graph(CYCLE_PKG)
    check = check_dependency(result, importer="packcycle.a", imported="packcycle.a")
    assert check.would_create_or_enlarge is True


def test_mcp_tool_check_dependency() -> None:
    payload = tool_check_dependency(
        CYCLE_PKG, importer="packcycle.a", imported="packcycle.a"
    )
    assert payload["wouldCreateOrEnlargeCycle"] is True
    assert payload["ok"] is False


def test_mcp_tool_query_dependencies() -> None:
    payload = tool_query_dependencies(CYCLE_PKG, module="packcycle.a")
    assert "packcycle.b" in payload["dependencies"]


def test_mcp_legal_imports_requires_dsl(tmp_path: Path) -> None:
    pkg = tmp_path / "layerdemo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "domain.py").write_text("x = 1\n", encoding="utf-8")
    (pkg / "api.py").write_text("from layerdemo import domain\n", encoding="utf-8")
    (tmp_path / "repolens.yaml").write_text(
        """
schemaVersion: 1
boundaries:
  - name: domain
    path: layerdemo/domain*
    allowed_imports: []
  - name: api
    path: layerdemo/api*
    allowed_imports: [domain]
""",
        encoding="utf-8",
    )
    payload = tool_get_legal_imports(tmp_path, module="layerdemo.api")
    assert payload["boundary"] == "api"
    assert "domain" in payload["allowedBoundaryNames"]


def test_architecture_doc_unique_names() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ArchitectureDoc(
            boundaries=[
                Boundary(name="x", path="a/**"),
                Boundary(name="x", path="b/**"),
            ]
        )
