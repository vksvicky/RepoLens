"""CLI: ``repolens check --diff`` cyclicity ratchet (G2)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from repolens.cli import app
from repolens.cli.commands_check import resolve_diff_base
from repolens.graph.baseline import DEFAULT_BASELINE_PATH

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


def test_resolve_diff_base_cli_wins(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    assert resolve_diff_base(cli_base="feature-base") == "feature-base"


def test_resolve_diff_base_github_base_ref(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    assert resolve_diff_base(cli_base=None) == "origin/main"
    monkeypatch.setenv("GITHUB_BASE_REF", "origin/develop")
    assert resolve_diff_base(cli_base=None) == "origin/develop"


def test_resolve_diff_base_merge_base_then_head_parent(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        calls.append(list(cmd))
        from subprocess import CompletedProcess

        if cmd[:3] == ["git", "merge-base", "HEAD"] and cmd[3] == "origin/main":
            return CompletedProcess(cmd, 0, stdout="abc123\n", stderr="")
        return CompletedProcess(cmd, 1, stdout="", stderr="")

    with patch("repolens.cli.commands_check.subprocess.run", side_effect=fake_run):
        assert resolve_diff_base(cli_base=None, cwd=tmp_path) == "abc123"


def test_resolve_diff_base_fallback_none(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        from subprocess import CompletedProcess

        return CompletedProcess(cmd, 1, stdout="", stderr="")

    with patch("repolens.cli.commands_check.subprocess.run", side_effect=fake_run):
        assert resolve_diff_base(cli_base=None, cwd=tmp_path) is None



def test_resolve_diff_base_rejects_unsafe_cli_base(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    assert resolve_diff_base(cli_base="main; rm -rf /") is None
    assert resolve_diff_base(cli_base="--output=/tmp/x") is None
    assert resolve_diff_base(cli_base="-C/tmp") is None


def test_git_diff_text_rejects_unsafe_base(tmp_path: Path) -> None:
    from subprocess import CompletedProcess
    from repolens.cli import commands_check as mod

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        calls.append(list(cmd))
        return CompletedProcess(cmd, 0, stdout="diff", stderr="")

    with patch("repolens.cli.commands_check.subprocess.run", side_effect=fake_run):
        assert mod._git_diff_text(cwd=tmp_path, base="evil;id") == ""
        assert calls == []
        assert mod._git_diff_text(cwd=tmp_path, base="origin/main") == "diff"
        assert calls == [["git", "diff", "origin/main...HEAD"]]


def test_check_requires_diff_flag(tmp_path: Path) -> None:
    result = runner.invoke(app, ["check", "--path", str(tmp_path)])
    assert result.exit_code == 2, result.output
    assert "--diff" in result.output.lower() or "diff" in result.output.lower()


def test_check_missing_baseline_soft_skip(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "check",
            "--diff",
            "--path",
            str(tmp_path),
            "--baseline",
            str(tmp_path / "missing.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "baseline" in result.output.lower()
    assert "skip" in result.output.lower() or "warn" in result.output.lower() or "no baseline" in result.output.lower()


def test_check_missing_baseline_require_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "check",
            "--diff",
            "--path",
            str(tmp_path),
            "--baseline",
            str(tmp_path / "missing.json"),
            "--require-baseline",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "baseline set" in result.output.lower() or "no baseline" in result.output.lower()


def test_check_missing_baseline_config_require(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".repolens.toml").write_text(
        "[graph]\nrequire_baseline = true\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["check", "--diff", "--path", str(root)])
    assert result.exit_code == 2, result.output


def test_check_no_breach_exit_0(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    set_r = runner.invoke(
        app,
        ["baseline", "set", "--path", str(CYCLE_PKG), "--out", str(baseline)],
    )
    assert set_r.exit_code == 0, set_r.output

    result = runner.invoke(
        app,
        [
            "check",
            "--diff",
            "--path",
            str(CYCLE_PKG),
            "--baseline",
            str(baseline),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "unchanged" in result.output.lower() or "cyclicity" in result.output.lower()


def test_check_breach_exit_1(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    _write_low_baseline(baseline, cyclicity=0)

    result = runner.invoke(
        app,
        [
            "check",
            "--diff",
            "--path",
            str(CYCLE_PKG),
            "--baseline",
            str(baseline),
        ],
    )
    assert result.exit_code == 1, result.output
    assert "ratchet breach" in result.output.lower()
    assert "+" in result.output  # fingerprint added lines


def test_check_breach_unanchored_note_when_no_git(tmp_path: Path) -> None:
    """Breach still exits 1 and emits ratchet.unanchored when anchor cannot run."""
    baseline = tmp_path / "baseline.json"
    _write_low_baseline(baseline, cyclicity=0)

    with patch(
        "repolens.cli.commands_check._git_available",
        return_value=False,
    ):
        result = runner.invoke(
            app,
            [
                "check",
                "--diff",
                "--path",
                str(CYCLE_PKG),
                "--baseline",
                str(baseline),
            ],
        )
    assert result.exit_code == 1, result.output
    assert "ratchet.unanchored:" in result.output
    assert "ratchet breach" in result.output.lower()


def test_check_graph_failed_exit_3(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    _write_low_baseline(baseline, cyclicity=0)
    result = runner.invoke(
        app,
        [
            "check",
            "--diff",
            "--path",
            str(tmp_path),
            "--baseline",
            str(baseline),
        ],
    )
    assert result.exit_code == 3, result.output


def test_check_graph_skipped_exit_3(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    pkg = root / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / ".repolens.toml").write_text("[graph]\nenabled = false\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    _write_low_baseline(baseline, cyclicity=0)
    result = runner.invoke(
        app,
        [
            "check",
            "--diff",
            "--path",
            str(root),
            "--baseline",
            str(baseline),
        ],
    )
    assert result.exit_code == 3, result.output


def test_check_prints_config_mismatch_note(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    _write_low_baseline(baseline, cyclicity=0)
    # Flip local_imports vs snapshot in baseline
    root = tmp_path / "proj"
    root.mkdir()
    pkg = root / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("from mypkg import b\n", encoding="utf-8")
    (pkg / "b.py").write_text("from mypkg import a\n", encoding="utf-8")
    (root / ".repolens.toml").write_text(
        '[graph]\nlocal_imports = "include"\n',
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "check",
            "--diff",
            "--path",
            str(root),
            "--baseline",
            str(baseline),
        ],
    )
    assert result.exit_code == 1, result.output
    assert "ratchet.config_mismatch" in result.output


def test_check_breach_anchors_and_gha_error(
    tmp_path: Path, monkeypatch
) -> None:
    baseline = tmp_path / "baseline.json"
    _write_low_baseline(baseline, cyclicity=0)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    diff_text = (
        "diff --git a/packcycle/a.py b/packcycle/a.py\n"
        "--- a/packcycle/a.py\n"
        "+++ b/packcycle/a.py\n"
        "@@ -1,0 +1,1 @@\n"
        "+from packcycle import b\n"
    )

    with (
        patch(
            "repolens.cli.commands_check.resolve_diff_base",
            return_value="origin/main",
        ),
        patch(
            "repolens.cli.commands_check._git_diff_text",
            return_value=diff_text,
        ),
        patch(
            "repolens.cli.commands_check._git_available",
            return_value=True,
        ),
    ):
        result = runner.invoke(
            app,
            [
                "check",
                "--diff",
                "--path",
                str(CYCLE_PKG),
                "--baseline",
                str(baseline),
            ],
        )
    assert result.exit_code == 1, result.output
    assert "packcycle/a.py:1" in result.output
    assert "::error" in result.output
    assert "file=packcycle/a.py" in result.output


def test_check_uses_default_baseline_path(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    pkg = root / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("x = 1\n", encoding="utf-8")
    set_r = runner.invoke(app, ["baseline", "set", "--path", str(root)])
    assert set_r.exit_code == 0, set_r.output
    assert (root / DEFAULT_BASELINE_PATH).is_file()

    result = runner.invoke(app, ["check", "--diff", "--path", str(root)])
    assert result.exit_code == 0, result.output
