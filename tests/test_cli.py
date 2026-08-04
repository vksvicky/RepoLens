"""CLI commands — dry-run path and version (no LLM network)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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
    assert "Inventory:" in result.output


def test_review_quiet_hides_progress(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print(1)\n", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "review",
            "--path",
            str(tmp_path),
            "--out",
            str(tmp_path / "out"),
            "--dry-run",
            "--quiet",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Inventory:" not in result.output
    assert "Source:" not in result.output


def test_review_verbose_shows_sample(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print(1)\n", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "review",
            "--path",
            str(tmp_path),
            "--out",
            str(tmp_path / "out"),
            "--dry-run",
            "--verbose",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "sample:" in result.output


def test_review_quiet_and_verbose_conflict(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["review", "--path", str(tmp_path), "--dry-run", "--quiet", "--verbose"],
    )
    assert result.exit_code == 2
    assert "quiet" in result.output.lower()


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
    with patch("repolens.llm.list_ollama_models", return_value=["qwen2.5:7b"]):
        result = runner.invoke(app, ["init", "--provider", "ollama", "--force"])
    assert result.exit_code == 0, result.output
    cfg = tmp_path / "xdg" / "repolens" / "config.toml"
    assert cfg.is_file()
    text = cfg.read_text(encoding="utf-8")
    assert 'provider = "ollama"' in text
    assert 'model = "qwen2.5:7b"' in text
    assert "Using installed Ollama model" in result.output


def test_init_ollama_respects_explicit_model(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    with patch("repolens.llm.list_ollama_models", return_value=["qwen2.5:7b"]):
        result = runner.invoke(
            app,
            ["init", "--provider", "ollama", "--model", "mistral", "--force"],
        )
    assert result.exit_code == 0, result.output
    text = (tmp_path / "xdg" / "repolens" / "config.toml").read_text(encoding="utf-8")
    assert 'model = "mistral"' in text


def test_review_no_provider_prints_init_hints(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")
    with patch("repolens.llm.detect_ollama", return_value=True):
        result = runner.invoke(
            app,
            ["review", "--path", str(tmp_path), "--out", str(tmp_path / "out")],
        )
    assert result.exit_code == 0, result.output
    assert "No model provider configured." in result.output
    assert "Detected Ollama" in result.output


def test_review_empty_path_exit_2() -> None:
    result = runner.invoke(app, ["review", "--path", "", "--dry-run"])
    assert result.exit_code == 2, result.output
    assert "--path is empty" in result.output


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


def test_hf_and_github_conflict() -> None:
    result = runner.invoke(
        app,
        ["review", "--github", "o/r", "--hf", "org/model", "--dry-run"],
    )
    assert result.exit_code == 2


def test_review_help_includes_deep_flags() -> None:
    result = runner.invoke(app, ["review", "--help"])
    assert result.exit_code == 0
    assert "--deep" in result.output
    assert "--no-deep" in result.output


def test_sentinel_and_architecture_help_include_deep() -> None:
    for cmd in ("sentinel", "architecture"):
        result = runner.invoke(app, [cmd, "--help"])
        assert result.exit_code == 0, result.output
        assert "--deep" in result.output
        assert "--no-deep" in result.output
