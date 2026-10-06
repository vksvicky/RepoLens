"""Optional quality counts for baseline.json (C4)."""

from __future__ import annotations

from pathlib import Path

from repolens.config import load_config
from repolens.graph import analyse_python_graph
from repolens.quality_metrics import measure_quality_metrics


def test_measure_quality_metrics_counts_boundary_violations(tmp_path: Path) -> None:
    pkg = tmp_path / "packcycle"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("from packcycle import b\n", encoding="utf-8")
    (pkg / "b.py").write_text("from packcycle import a\n", encoding="utf-8")
    (tmp_path / "repolens.yaml").write_text(
        """
schemaVersion: 1
boundaries:
  - name: a_layer
    path: packcycle/a*
    allowed_imports: []
  - name: b_layer
    path: packcycle/b*
    allowed_imports: [a_layer]
""",
        encoding="utf-8",
    )
    cfg = load_config(tmp_path)
    graph = analyse_python_graph(tmp_path, config=cfg.graph)
    metrics = measure_quality_metrics(tmp_path, cfg, graph)
    assert metrics["boundaryViolations"] >= 1
    assert metrics["complexityHotspots"] >= 0
    assert metrics["nearClonePairs"] >= 0


def test_measure_quality_metrics_zero_without_architecture(tmp_path: Path) -> None:
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("x = 1\n", encoding="utf-8")
    cfg = load_config(tmp_path)
    graph = analyse_python_graph(tmp_path, config=cfg.graph)
    metrics = measure_quality_metrics(tmp_path, cfg, graph)
    assert metrics["boundaryViolations"] == 0
    assert metrics["complexityHotspots"] == 0
    assert metrics["nearClonePairs"] == 0


def test_measure_quality_metrics_invalid_architecture_skips_boundaries(
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "repolens.yaml").write_text("[]\n", encoding="utf-8")
    cfg = load_config(tmp_path)
    graph = analyse_python_graph(tmp_path, config=cfg.graph)
    metrics = measure_quality_metrics(tmp_path, cfg, graph)
    assert metrics["boundaryViolations"] == 0
