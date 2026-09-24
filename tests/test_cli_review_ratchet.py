"""CLI: ``repolens review --ratchet`` exit integration (G2)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from repolens.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"
CYCLE_PKG = FIXTURES / "graph_cycle_pkg"


def _write_low_baseline(path: Path, *, cyclicity: int = 0) -> None:
    doc = {
        "schemaVersion": 1,
        "kind": "cyclicity",
        "generatedAt": "2026-09-24T00:00:00Z",
        "repolensVersion": "0.0.0-test",
        "graph": {
            "engine": "grimp",
            "packages": ["packcycle"],
            "moduleCount": 2,
            "cyclicity": cyclicity,
            "cycleCount": 0,
            "fingerprints": [],
        },
        "configSnapshot": {
            "type_only": "ignore",
            "local_imports": "exclude",
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def test_review_ratchet_breach_exit_1(tmp_path: Path) -> None:
    """scanners-only review on cycle fixture + baseline cyclicity 0 → exit 1."""
    root = tmp_path / "proj"
    shutil.copytree(
        CYCLE_PKG,
        root,
        ignore=shutil.ignore_patterns(".repolens"),
    )
    _write_low_baseline(root / ".repolens" / "baseline.json", cyclicity=0)

    result = runner.invoke(
        app,
        [
            "review",
            "--path",
            str(root),
            "--out",
            str(tmp_path / "out"),
            "--scanners-only",
            "--scanners",
            "off",
            "--ratchet",
        ],
    )
    assert result.exit_code == 1, result.output
    assert "ratchet breach" in result.output.lower()


def test_review_config_ratchet_breach_exit_1(tmp_path: Path) -> None:
    """[graph].ratchet = true enables the same exit-1 gate without --ratchet."""
    root = tmp_path / "proj"
    shutil.copytree(
        CYCLE_PKG,
        root,
        ignore=shutil.ignore_patterns(".repolens"),
    )
    _write_low_baseline(root / ".repolens" / "baseline.json", cyclicity=0)
    (root / ".repolens.toml").write_text(
        "[graph]\nratchet = true\n", encoding="utf-8"
    )

    result = runner.invoke(
        app,
        [
            "review",
            "--path",
            str(root),
            "--out",
            str(tmp_path / "out"),
            "--scanners-only",
            "--scanners",
            "off",
        ],
    )
    assert result.exit_code == 1, result.output
    assert "ratchet breach" in result.output.lower()


def test_review_without_ratchet_does_not_exit_1_on_cycles(tmp_path: Path) -> None:
    """Cycles alone do not fail review when ratchet is off."""
    root = tmp_path / "proj"
    shutil.copytree(
        CYCLE_PKG,
        root,
        ignore=shutil.ignore_patterns(".repolens"),
    )
    _write_low_baseline(root / ".repolens" / "baseline.json", cyclicity=0)

    result = runner.invoke(
        app,
        [
            "review",
            "--path",
            str(root),
            "--out",
            str(tmp_path / "out"),
            "--scanners-only",
            "--scanners",
            "off",
        ],
    )
    assert result.exit_code == 0, result.output
