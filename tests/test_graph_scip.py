"""#95 SCIP JSON ingest and analyse_repo_graph merge."""

from __future__ import annotations

import json
from pathlib import Path

from repolens.config import GraphConfig
from repolens.graph import analyse_python_graph, analyse_repo_graph
from repolens.graph.scip import load_scip_json
from repolens.graph.types import GraphStatus


def test_analyse_python_graph_still_imported() -> None:
    assert callable(analyse_python_graph)


def test_scip_import_role_line_is_one_based(tmp_path: Path) -> None:
    payload = {
        "documents": [
            {
                "relative_path": "src/a.ts",
                "occurrences": [
                    {
                        "symbol": "scip-typescript npm pkg 1 src/b.ts",
                        "symbol_roles": 1,
                        "range": [2, 0, 2, 8],
                    }
                ],
            }
        ]
    }
    path = tmp_path / "index.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = load_scip_json(path)
    assert result.status is GraphStatus.OK
    assert len(result.edges) == 1
    assert result.edges[0].importer == "src/a.ts"
    assert result.edges[0].imported == "scip-typescript npm pkg 1 src/b.ts"
    assert result.edges[0].line == 3


def test_scip_skips_non_import_roles(tmp_path: Path) -> None:
    payload = {
        "documents": [
            {
                "relativePath": "src/a.ts",
                "occurrences": [
                    {"symbol": "local", "symbolRoles": 0, "range": [0, 0, 0, 1]}
                ],
            }
        ]
    }
    path = tmp_path / "index.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = load_scip_json(path)
    assert result.edges == []


def test_scip_invalid_json_is_failed_source(tmp_path: Path) -> None:
    path = tmp_path / "index.scip"
    path.write_bytes(b"\x00\x01not-json")
    result = load_scip_json(path)
    assert result.status is GraphStatus.FAILED
    assert result.durability_gaps
    missing = load_scip_json(tmp_path / "nope.json")
    assert missing.status is GraphStatus.FAILED
    listed = tmp_path / "arr.json"
    listed.write_text("[]", encoding="utf-8")
    assert load_scip_json(listed).status is GraphStatus.FAILED


def test_repo_graph_merges_scip_and_python(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("from pkg import b\n", encoding="utf-8")
    (pkg / "b.py").write_text("x = 1\n", encoding="utf-8")
    scip = tmp_path / "scip.json"
    scip.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "relative_path": "src/js.ts",
                        "occurrences": [
                            {
                                "symbol": "other.ts",
                                "symbol_roles": 1,
                                "range": [0, 0, 0, 1],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = analyse_repo_graph(
        tmp_path, config=GraphConfig(packages=["pkg"], scip="scip.json")
    )
    importers = {e.importer for e in result.edges}
    assert "pkg.a" in importers or any("pkg.a" in e.importer for e in result.edges)
    assert any(e.importer == "src/js.ts" for e in result.edges)


def test_repo_graph_extra_edges_and_escape(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("x = 1\n", encoding="utf-8")
    edges = tmp_path / "edges.json"
    edges.write_text(
        '[{"importer": "src/a.ts", "imported": "src/b.ts", "line": 1}]',
        encoding="utf-8",
    )
    ok = analyse_repo_graph(
        tmp_path, config=GraphConfig(packages=["pkg"], extra_edges="edges.json")
    )
    assert any(e.importer == "src/a.ts" for e in ok.edges)
    escaped = analyse_repo_graph(
        tmp_path,
        config=GraphConfig(packages=["pkg"], scip="../outside.json"),
    )
    assert any("escapes" in g for g in escaped.durability_gaps)

