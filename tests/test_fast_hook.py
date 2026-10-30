"""``repolens hook fast`` is Fast Brain before commit, with no report left behind."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from repolens.cli import app

runner = CliRunner()
_ROOT = Path(__file__).resolve().parents[1]
_HOOKS = _ROOT / ".pre-commit-hooks.yaml"
_CI = _ROOT / "docs" / "ci.md"


def _long_function() -> str:
    body = "\n".join(f"    value = {number}" for number in range(78))
    return f"def process_data():\n{body}\n    return value\n"


def test_pre_commit_hook_file_is_fast_brain_only() -> None:
    text = _HOOKS.read_text(encoding="utf-8")
    assert "id: repolens-fast" in text
    assert "entry: repolens hook fast" in text
    assert "pass_filenames: false" in text
    assert "always_run: true" in text
    lowered = text.lower()
    for banned in ("trivy", "semgrep", "gitleaks", "--preset pr", "types:"):
        assert banned not in lowered


def test_hook_blocks_a_large_function_and_leaves_no_report(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text(_long_function(), encoding="utf-8")
    result = runner.invoke(app, ["hook", "fast", "--path", str(root)])
    assert result.exit_code == 1, result.output
    assert "app.py:1:" in result.output
    assert "process_data" in result.output
    assert not (root / "reports").exists()
    assert not (root / ".repolens").exists()


def test_hook_passes_a_short_tree(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text(
        "def add(left, right):\n    return left + right\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["hook", "fast", "--path", str(root)])
    assert result.exit_code == 0, result.output
    assert not (root / "reports").exists()


def test_hook_still_fails_when_triage_routing_is_on(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text(_long_function(), encoding="utf-8")
    (root / ".repolens.toml").write_text("[ci]\ntriage_routing = true\n", encoding="utf-8")
    result = runner.invoke(app, ["hook", "fast", "--path", str(root)])
    assert result.exit_code == 1, result.output
    assert "app.py:1:" in result.output


def test_ci_doc_describes_the_fast_hook() -> None:
    text = _CI.read_text(encoding="utf-8")
    assert "repolens hook fast" in text
    assert "id: repolens-fast" in text
    assert "rev: v0.1.6" in text
    assert "Pin `rev` to `v0.1.6`." in text
