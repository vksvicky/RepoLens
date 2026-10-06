"""Merged repo graph must preserve FAILED/SKIPPED exit semantics for CLI gates."""

from __future__ import annotations

from pathlib import Path

from repolens.config import GraphConfig, load_config
from repolens.graph.merge import merge_graph_results
from repolens.graph.repo import analyse_repo_graph
from repolens.graph.types import GraphResult, GraphStatus


def test_empty_root_stays_failed(tmp_path: Path) -> None:
    result = analyse_repo_graph(tmp_path)
    assert result.status is GraphStatus.FAILED
    assert any("no_python_packages" in g for g in result.durability_gaps)


def test_graph_disabled_stays_skipped(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    pkg = root / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / ".repolens.toml").write_text("[graph]\nenabled = false\n", encoding="utf-8")
    cfg = load_config(root)
    result = analyse_repo_graph(root, config=cfg.graph)
    assert result.status is GraphStatus.SKIPPED
    assert any("disabled" in g for g in result.durability_gaps)


def test_merge_failed_plus_skipped_no_edges_is_failed() -> None:
    merged = merge_graph_results(
        [
            GraphResult(
                status=GraphStatus.FAILED,
                durability_gaps=["graph.no_python_packages"],
            ),
            GraphResult(status=GraphStatus.SKIPPED),
        ],
        config=GraphConfig(),
    )
    assert merged.status is GraphStatus.FAILED


def test_merge_ok_with_no_edges_stays_ok() -> None:
    merged = merge_graph_results(
        [
            GraphResult(status=GraphStatus.OK, packages=["mypkg"]),
            GraphResult(status=GraphStatus.SKIPPED),
        ],
        config=GraphConfig(),
    )
    assert merged.status is GraphStatus.OK
    assert merged.packages == ["mypkg"]
