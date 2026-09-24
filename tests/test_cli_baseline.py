"""CLI: ``repolens baseline set`` / ``show`` (G2)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from repolens.cli import app
from repolens.graph.baseline import DEFAULT_BASELINE_PATH

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"
CYCLE_PKG = FIXTURES / "graph_cycle_pkg"


def test_baseline_set_writes_file(tmp_path: Path) -> None:
    out = tmp_path / "baseline.json"
    result = runner.invoke(
        app,
        ["baseline", "set", "--path", str(CYCLE_PKG), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["kind"] == "cyclicity"
    assert doc["graph"]["cyclicity"] >= 4
    assert len(doc["graph"]["fingerprints"]) >= 1
    assert "Wrote" in result.output or "wrote" in result.output.lower()


def test_baseline_set_failed_exits_3(tmp_path: Path) -> None:
    out = tmp_path / "baseline.json"
    result = runner.invoke(
        app,
        ["baseline", "set", "--path", str(tmp_path), "--out", str(out)],
    )
    assert result.exit_code == 3, result.output
    assert not out.exists()


def test_baseline_show_prints_cyclicity_and_fingerprints(tmp_path: Path) -> None:
    out = tmp_path / "baseline.json"
    set_result = runner.invoke(
        app,
        ["baseline", "set", "--path", str(CYCLE_PKG), "--out", str(out)],
    )
    assert set_result.exit_code == 0, set_result.output

    show = runner.invoke(
        app,
        ["baseline", "show", "--path", str(CYCLE_PKG), "--out", str(out)],
    )
    assert show.exit_code == 0, show.output
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert str(doc["graph"]["cyclicity"]) in show.output
    assert str(len(doc["graph"]["fingerprints"])) in show.output
    assert str(out) in show.output or out.name in show.output


def test_baseline_set_uses_config_baseline_path(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    pkg = root / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("from mypkg import b\n", encoding="utf-8")
    (pkg / "b.py").write_text("from mypkg import a\n", encoding="utf-8")
    (root / ".repolens.toml").write_text(
        '[graph]\nbaseline_path = "custom/base.json"\n',
        encoding="utf-8",
    )
    result = runner.invoke(app, ["baseline", "set", "--path", str(root)])
    assert result.exit_code == 0, result.output
    written = root / "custom" / "base.json"
    assert written.is_file()
    doc = json.loads(written.read_text(encoding="utf-8"))
    assert doc["graph"]["cyclicity"] >= 4


def test_baseline_set_default_path(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    pkg = root / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("x = 1\n", encoding="utf-8")
    result = runner.invoke(app, ["baseline", "set", "--path", str(root)])
    assert result.exit_code == 0, result.output
    written = root / DEFAULT_BASELINE_PATH
    assert written.is_file()


def test_baseline_show_missing_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "baseline",
            "show",
            "--path",
            str(tmp_path),
            "--out",
            str(tmp_path / "missing.json"),
        ],
    )
    assert result.exit_code == 2, result.output
    assert "baseline set" in result.output.lower() or "no baseline" in result.output.lower()
