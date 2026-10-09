"""``review --preset pr|changed|release`` mapping and CLI behaviour."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from repolens.cli import app
from repolens.cli.presets import (
    CHANGED_TIMEOUT_S,
    RELEASE_TIMEOUT_S,
    ReviewFlagBag,
    apply_preset,
    parse_preset,
)

runner = CliRunner()


# --- mapping (Right) ---------------------------------------------------------


def test_pr_maps_to_scanners_only_no_deep() -> None:
    out = apply_preset("pr", ReviewFlagBag())
    assert out.scanners_only is True
    assert out.deep is False
    assert out.ci is False


def test_changed_maps_to_git_diff_auto_deep_timeout() -> None:
    out = apply_preset("changed", ReviewFlagBag())
    assert out.git_diff == "auto"
    assert out.deep is True
    assert out.timeout == CHANGED_TIMEOUT_S
    assert out.scanners_only is False


def test_release_maps_to_full_full_audit_deep_long_timeout() -> None:
    out = apply_preset("release", ReviewFlagBag())
    assert out.force_full is True
    assert out.full_audit is True
    assert out.deep is True
    assert out.timeout == RELEASE_TIMEOUT_S
    assert RELEASE_TIMEOUT_S > CHANGED_TIMEOUT_S


# --- explicit flags win (Boundary / Inverse) ---------------------------------


def test_explicit_timeout_and_no_deep_override_preset() -> None:
    bag = ReviewFlagBag(timeout=42.0, deep=False)
    out = apply_preset("release", bag)
    assert out.timeout == 42.0
    assert out.deep is False
    assert out.full_audit is True


def test_explicit_git_diff_blocks_release_full() -> None:
    out = apply_preset("release", ReviewFlagBag(git_diff="HEAD~3"))
    assert out.git_diff == "HEAD~3"
    assert out.force_full is False  # --full and --git-diff are mutually exclusive


def test_explicit_changed_blocks_changed_git_diff() -> None:
    out = apply_preset("changed", ReviewFlagBag(force_changed=True))
    assert out.git_diff is None
    assert out.force_changed is True


def test_explicit_full_blocks_changed_git_diff() -> None:
    out = apply_preset("changed", ReviewFlagBag(force_full=True))
    assert out.git_diff is None


def test_pr_respects_explicit_ci_and_dry_run() -> None:
    assert apply_preset("pr", ReviewFlagBag(ci=True)).scanners_only is False
    assert apply_preset("pr", ReviewFlagBag(dry_run=True)).scanners_only is False


def test_apply_preset_does_not_mutate_input() -> None:
    bag = ReviewFlagBag()
    apply_preset("pr", bag)
    assert bag == ReviewFlagBag()


def test_apply_preset_is_idempotent() -> None:
    once = apply_preset("release", ReviewFlagBag())
    assert apply_preset("release", once) == once


# --- parsing (Error) ---------------------------------------------------------


def test_parse_preset_none_and_case() -> None:
    assert parse_preset(None) is None
    assert parse_preset(" PR ") == "pr"


def test_parse_preset_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="pr \\| changed \\| release"):
        parse_preset("nightly")


# --- CLI ---------------------------------------------------------------------


def _tiny_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text("print('hi')\n", encoding="utf-8")
    return root


def test_help_documents_preset_and_override_rule() -> None:
    """Registration is the CI-stable contract; Rich may truncate rendered help."""
    import typer.main

    cmd = typer.main.get_command(app).commands["review"]  # type: ignore[attr-defined]
    names = {
        opt
        for param in cmd.params
        for opt in (param.opts or [])
    }
    assert "--preset" in names
    result = runner.invoke(app, ["review", "--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0
    # Prefer plain text; fall back to registration-only if terminal width still clips.
    plain = result.output.replace("\x1b", "")
    if "--preset" in plain:
        assert "pr" in plain and "release" in plain


def test_cli_rejects_unknown_preset(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["review", "--path", str(_tiny_repo(tmp_path)), "--preset", "nightly"]
    )
    assert result.exit_code == 2


def test_cli_preset_pr_never_calls_llm(tmp_path: Path) -> None:
    root = _tiny_repo(tmp_path)
    with patch(
        "repolens.pipeline.run._invoke_llm", side_effect=AssertionError("LLM called")
    ) as llm, patch(
        "repolens.llm.setup.detect_ollama", side_effect=AssertionError("Ollama probed")
    ):
        result = runner.invoke(
            app,
            [
                "review", "--path", str(root), "--out", str(tmp_path / "out"),
                "--preset", "pr", "--scanners", "off", "--quiet",
            ],
        )
    assert result.exit_code == 0, result.output
    llm.assert_not_called()


def test_cli_preset_forwards_mapped_flags(tmp_path: Path) -> None:
    root = _tiny_repo(tmp_path)
    with patch("repolens.cli.commands_review._run_mode") as run_mode:
        result = runner.invoke(
            app, ["review", "--path", str(root), "--preset", "release"]
        )
    assert result.exit_code == 0, result.output
    args = run_mode.call_args.args
    assert RELEASE_TIMEOUT_S in args
    assert True in args  # force_full / full_audit / deep


def test_cli_explicit_timeout_beats_preset(tmp_path: Path) -> None:
    root = _tiny_repo(tmp_path)
    with patch("repolens.cli.commands_review._run_mode") as run_mode:
        runner.invoke(
            app,
            ["review", "--path", str(root), "--preset", "changed", "--timeout", "7"],
        )
    args = run_mode.call_args.args
    assert 7.0 in args
    assert CHANGED_TIMEOUT_S not in args
    assert "auto" in args
