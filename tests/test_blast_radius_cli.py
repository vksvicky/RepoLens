"""Standalone ``repolens blast-radius`` query (#110)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from repolens.blast_radius import simulate_blast_radius
from repolens.cli import app

runner = CliRunner()


def _tiny_pkg(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    pkg = root / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "core.py").write_text("X = 1\n", encoding="utf-8")
    (pkg / "api.py").write_text("from pkg.core import X\n", encoding="utf-8")
    (pkg / "cli.py").write_text("from pkg.api import X\n", encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_api.py").write_text(
        "from pkg import api\n\ndef test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    return root


def test_simulate_blast_radius_transitive_consumers(tmp_path: Path) -> None:
    root = _tiny_pkg(tmp_path)
    sim = simulate_blast_radius(root, "pkg/core.py")
    assert sim.seed_module == "pkg.core"
    # api and cli both eventually depend on core
    assert "pkg.api" in sim.consumers
    assert "pkg.cli" in sim.consumers
    assert sim.consumer_count >= 2
    assert sim.graph_module_count >= 3
    assert 0 < sim.percent_of_graph <= 100
    assert sim.test_file_count >= 1 or "test" in sim.test_density_note.lower()


def test_cli_blast_radius_table_and_json(tmp_path: Path) -> None:
    root = _tiny_pkg(tmp_path)
    table = runner.invoke(
        app, ["blast-radius", "pkg/core.py", "--path", str(root)]
    )
    assert table.exit_code == 0, table.output
    assert "pkg.api" in table.output or "Consumers" in table.output

    js = runner.invoke(
        app, ["blast-radius", "pkg.core", "--path", str(root), "--json"]
    )
    assert js.exit_code == 0, js.output
    assert '"consumer_count"' in js.output or '"consumers"' in js.output
