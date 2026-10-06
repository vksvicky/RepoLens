"""CLI: ``repolens hotspots`` (C7)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from repolens.cli import app

runner = CliRunner()


def _repo_with_history(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "hot.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "hot.py"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "one"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "hot.py").write_text("x = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "hot.py"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "two"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path


def test_hotspots_json(tmp_path: Path) -> None:
    root = _repo_with_history(tmp_path)
    result = runner.invoke(
        app,
        ["hotspots", "--path", str(root), "--since", "10.years", "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert rows[0]["path"] == "hot.py"
    assert rows[0]["commits"] == 2


def test_hotspots_bad_since_exits_2(tmp_path: Path) -> None:
    root = _repo_with_history(tmp_path)
    result = runner.invoke(
        app,
        ["hotspots", "--path", str(root), "--since", "--all"],
    )
    assert result.exit_code == 2, result.output


def test_hotspots_not_git_exits_3(tmp_path: Path) -> None:
    result = runner.invoke(app, ["hotspots", "--path", str(tmp_path)])
    assert result.exit_code == 3, result.output
