from __future__ import annotations

import json

from repolens.config import GraphConfig
from repolens.graph.baseline import (
    baseline_from_graph,
    config_snapshot_from_graph_config,
    fingerprint_cycles,
    load_baseline,
    write_baseline,
)
from repolens.graph.types import CycleGroup, GraphResult, GraphStatus


def _sample_result(*, cyclicity: int = 8) -> GraphResult:
    return GraphResult(
        status=GraphStatus.OK,
        packages=["repolens", "app"],
        module_count=10,
        cyclicity=cyclicity,
        cycles=[
            CycleGroup(modules=("z.mod", "a.mod")),
            CycleGroup(modules=("m", "n", "o")),
            CycleGroup(modules=("solo",)),
        ],
    )


def test_fingerprint_sorted_and_stable():
    result = _sample_result()
    fps = fingerprint_cycles(result)
    assert fps == [["a.mod", "z.mod"], ["m", "n", "o"]]
    assert fps == sorted(fps)


def test_fingerprint_excludes_singleton_scc():
    result = GraphResult(
        status=GraphStatus.OK,
        cycles=[CycleGroup(modules=("only",))],
        cyclicity=0,
    )
    assert fingerprint_cycles(result) == []


def test_config_snapshot_from_graph_config():
    cfg = GraphConfig(type_only="warn", local_imports="include")
    assert config_snapshot_from_graph_config(cfg) == {
        "type_only": "warn",
        "local_imports": "include",
    }


def test_baseline_from_graph_fields():
    result = _sample_result(cyclicity=8)
    doc = baseline_from_graph(result, config=GraphConfig(), version="0.0.0-test")
    assert doc["schemaVersion"] == 1
    assert doc["kind"] == "cyclicity"
    assert doc["repolensVersion"] == "0.0.0-test"
    assert doc["generatedAt"].endswith("Z")
    graph = doc["graph"]
    assert graph["engine"] == "grimp"
    assert graph["packages"] == ["repolens", "app"]
    assert graph["moduleCount"] == 10
    assert graph["cyclicity"] == 8
    assert graph["cycleCount"] == 2
    assert graph["fingerprints"] == [["a.mod", "z.mod"], ["m", "n", "o"]]
    assert doc["configSnapshot"] == {
        "type_only": "ignore",
        "local_imports": "exclude",
    }


def test_round_trip_tmp_path(tmp_path):
    result = _sample_result()
    doc = baseline_from_graph(result, config=GraphConfig(), version="0.0.0-test")
    path = tmp_path / "baseline.json"
    write_baseline(path, doc)
    loaded = load_baseline(path)
    assert loaded["graph"]["cyclicity"] == doc["graph"]["cyclicity"]
    assert loaded["graph"]["fingerprints"] == doc["graph"]["fingerprints"]
    assert loaded["configSnapshot"] == {
        "type_only": "ignore",
        "local_imports": "exclude",
    }


def test_write_baseline_sorted_keys_and_trailing_newline(tmp_path):
    doc = baseline_from_graph(_sample_result(), config=GraphConfig(), version="1")
    path = tmp_path / "baseline.json"
    write_baseline(path, doc)
    raw = path.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert not raw.endswith("\n\n")
    parsed = json.loads(raw)
    assert list(parsed.keys()) == sorted(parsed.keys())
    assert raw == json.dumps(parsed, sort_keys=True, indent=2) + "\n"
