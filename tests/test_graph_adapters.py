import json
from pathlib import Path

import pytest

from repolens.config import GraphConfig
from repolens.graph import analyse_python_graph
from repolens.graph.adapters import load_precomputed_edges
from repolens.graph.types import EdgeKind, GraphStatus, ImportScope

FIXTURES = Path(__file__).parent / "fixtures"


def test_two_node_cycle_from_json(tmp_path: Path):
    path = tmp_path / "edges.json"
    path.write_text(
        json.dumps(
            [
                {"importer": "a", "imported": "b"},
                {"importer": "b", "imported": "a"},
            ]
        ),
        encoding="utf-8",
    )
    result = load_precomputed_edges(path)
    assert result.status is GraphStatus.OK
    assert len(result.cycles) == 1
    assert set(result.cycles[0].modules) == {"a", "b"}
    assert result.cyclicity == 4
    assert result.module_count == 2


def test_acyclic_json(tmp_path: Path):
    path = tmp_path / "edges.json"
    path.write_text(
        json.dumps([{"importer": "a", "imported": "b"}, {"importer": "b", "imported": "c"}]),
        encoding="utf-8",
    )
    result = load_precomputed_edges(path)
    assert result.cycles == []
    assert result.cyclicity == 0


def test_missing_file(tmp_path: Path):
    result = load_precomputed_edges(tmp_path / "missing.json")
    assert result.status is GraphStatus.FAILED
    assert any("not found" in g for g in result.durability_gaps)


def test_invalid_json(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    result = load_precomputed_edges(path)
    assert result.status is GraphStatus.FAILED
    assert any("invalid JSON" in g for g in result.durability_gaps)


def test_kind_and_scope_fields(tmp_path: Path):
    path = tmp_path / "edges.json"
    path.write_text(
        json.dumps(
            [
                {
                    "importer": "a",
                    "imported": "b",
                    "kind": "type_only",
                    "scope": "function_local",
                    "line": 3,
                },
            ]
        ),
        encoding="utf-8",
    )
    result = load_precomputed_edges(path)
    assert len(result.edges) == 1
    edge = result.edges[0]
    assert edge.kind is EdgeKind.TYPE_ONLY
    assert edge.scope is ImportScope.FUNCTION_LOCAL
    assert edge.line == 3
    assert result.gated_edges == []


def test_cross_check_matches_grimp_fixture(tmp_path: Path):
    root = FIXTURES / "graph_cycle_pkg"
    grimp_result = analyse_python_graph(root)
    path = tmp_path / "edges.json"
    path.write_text(
        json.dumps(
            [
                {
                    "importer": e.importer,
                    "imported": e.imported,
                    "kind": e.kind.value,
                    "scope": e.scope.value,
                    "line": e.line,
                }
                for e in grimp_result.gated_edges
            ]
        ),
        encoding="utf-8",
    )
    adapter_result = load_precomputed_edges(path)
    assert [c.modules for c in grimp_result.cycles] == [c.modules for c in adapter_result.cycles]
    assert grimp_result.cyclicity == adapter_result.cyclicity


def test_bad_edge_records_gap(tmp_path: Path):
    path = tmp_path / "edges.json"
    path.write_text(json.dumps([{"imported": "b"}]), encoding="utf-8")
    result = load_precomputed_edges(path)
    assert result.status is GraphStatus.PARTIAL
    assert any("importer" in g for g in result.durability_gaps)
    assert result.edges == []


def test_local_import_gate_respects_config(tmp_path: Path):
    path = tmp_path / "edges.json"
    path.write_text(
        json.dumps(
            [
                {"importer": "a", "imported": "b", "scope": "function_local"},
                {"importer": "b", "imported": "a"},
            ]
        ),
        encoding="utf-8",
    )
    excluded = load_precomputed_edges(path)
    assert excluded.cycles == []
    included = load_precomputed_edges(path, config=GraphConfig(local_imports="include"))
    assert len(included.cycles) == 1
