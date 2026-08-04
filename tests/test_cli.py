"""CLI commands — dry-run path and version (no LLM network)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from repolens import __version__
from repolens.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_review_dry_run_writes_report(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print(1)\n", encoding="utf-8")
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["review", "--path", str(tmp_path), "--out", str(out), "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    reports = list(out.glob("gate_review_report_*.md"))
    assert len(reports) == 1
    assert "dry-run" in reports[0].read_text(encoding="utf-8")


def test_sentinel_dry_run(tmp_path: Path) -> None:
    (tmp_path / "x.py").write_text("x=1\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["sentinel", "--path", str(tmp_path), "--out", str(tmp_path / "r"), "--dry-run"],
    )
    assert result.exit_code == 0, result.output


def test_missing_path_exit_2(tmp_path: Path) -> None:
    result = runner.invoke(app, ["review", "--path", str(tmp_path / "missing"), "--dry-run"])
    assert result.exit_code == 2


def test_init_writes_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    result = runner.invoke(app, ["init", "--provider", "ollama", "--force"])
    assert result.exit_code == 0, result.output
    cfg = tmp_path / "xdg" / "repolens" / "config.toml"
    assert cfg.is_file()
    assert 'provider = "ollama"' in cfg.read_text(encoding="utf-8")


def test_export_prints_path(tmp_path: Path) -> None:
    report = tmp_path / "gate_review_report_2026-08-04.md"
    report.write_text("# report\n", encoding="utf-8")
    result = runner.invoke(app, ["export", str(report)])
    assert result.exit_code == 0
    assert "Report:" in result.output
    assert report.name in result.output.replace("\n", "")


def test_github_and_path_conflict(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["review", "--path", str(tmp_path), "--github", "o/r", "--dry-run"],
    )
    assert result.exit_code == 2
    assert "exactly one" in result.output.lower() or "Source error" in result.output


def test_github_dry_run_mocked(tmp_path: Path, monkeypatch) -> None:
    from unittest.mock import patch

    from repolens.sources import ResolvedSource

    fake = ResolvedSource(root=tmp_path, ephemeral=True, label="github:o/r")
    (tmp_path / "a.py").write_text("x=1\n", encoding="utf-8")
    out = tmp_path / "reports-out"
    with (
        patch("repolens.cli.resolve_source", return_value=fake),
        patch("repolens.cli.cleanup_source") as cleanup,
    ):
        result = runner.invoke(
            app,
            ["review", "--github", "o/r", "--out", str(out), "--dry-run"],
        )
    assert result.exit_code == 0, result.output
    cleanup.assert_called()
    assert list(out.glob("gate_review_report_*.md"))
