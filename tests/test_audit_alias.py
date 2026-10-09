"""``repolens audit`` = release due-diligence defaults (M1 #101)."""

from __future__ import annotations

from inspect import signature
from pathlib import Path
from unittest.mock import patch

import typer.main
from typer.testing import CliRunner

from repolens.cli import app
from repolens.cli.commands_review import _run_mode
from repolens.cli.presets import RELEASE_TIMEOUT_S

runner = CliRunner()


def _tiny_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text("print('hi')\n", encoding="utf-8")
    return root


def _bound_run_mode(run_mode_mock: object) -> dict:
    call = run_mode_mock.call_args  # type: ignore[attr-defined]
    return dict(signature(_run_mode).bind(*call.args, **call.kwargs).arguments)


def test_help_lists_audit_command() -> None:
    result = runner.invoke(app, ["--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0
    assert "audit" in result.output.lower()


def test_audit_help_mentions_due_diligence() -> None:
    result = runner.invoke(app, ["audit", "--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0
    plain = result.output.lower()
    assert "due-diligence" in plain or "release" in plain


def test_audit_applies_release_ratchet_and_verify(tmp_path: Path) -> None:
    root = _tiny_repo(tmp_path)
    with patch("repolens.cli.commands_review._run_mode") as run_mode:
        result = runner.invoke(app, ["audit", "--path", str(root)])
    assert result.exit_code == 0, result.output
    bound = _bound_run_mode(run_mode)
    assert bound["mode"] == "review"
    assert bound["force_full"] is True
    assert bound["full_audit"] is True
    assert bound["deep"] is True
    assert bound["timeout"] == RELEASE_TIMEOUT_S
    assert bound["ratchet"] is True
    assert bound["verify_findings"] is True
    assert bound["scanners_only"] is False
    assert bound["fmt"] == "md"


def test_audit_explicit_overrides_win(tmp_path: Path) -> None:
    root = _tiny_repo(tmp_path)
    with patch("repolens.cli.commands_review._run_mode") as run_mode:
        result = runner.invoke(
            app,
            [
                "audit", "--path", str(root), "--timeout", "11",
                "--no-ratchet", "--no-verify-findings", "--no-deep",
            ],
        )
    assert result.exit_code == 0, result.output
    bound = _bound_run_mode(run_mode)
    assert bound["timeout"] == 11.0
    assert bound["ratchet"] is False
    assert bound["verify_findings"] is False
    assert bound["deep"] is False
    assert bound["full_audit"] is True  # release kit still


def test_audit_registered_as_typer_command() -> None:
    cmd = typer.main.get_command(app).commands["audit"]  # type: ignore[attr-defined]
    names = {opt for param in cmd.params for opt in (param.opts or [])}
    assert "--timeout" in names
    assert "--ratchet" in names or "--no-ratchet" in names
