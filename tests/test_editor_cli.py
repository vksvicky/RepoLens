"""Editor-facing Fast Brain diagnostics and graph CLI (C1/C2/C5/C6)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from repolens.cli import app
from repolens.diagnostics import diagnostic_jsonl, diagnostic_sarif
from repolens.schema import Issue, Severity

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"
CYCLE_PKG = FIXTURES / "graph_cycle_pkg"


def _issue() -> Issue:
    return Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="quality.complexity",
        file="a.py",
        line=3,
        title="Hot function",
        explanation="e",
        impact="",
        recommendedFix="split",
        codeExample="",
        source="heuristic",
    )


def test_diagnostic_jsonl_and_sarif_shape(tmp_path: Path) -> None:
    issues = [_issue()]
    line = diagnostic_jsonl(issues).strip()
    row = json.loads(line)
    assert row["path"] == "a.py"
    assert row["ruleId"] == "quality.complexity"
    sarif = diagnostic_sarif(issues, root=tmp_path)
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"][0]["ruleId"] == "quality.complexity"


def test_check_format_sarif_uses_diagnostics(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    with patch(
        "repolens.diagnostics.collect_fast_issues",
        return_value=[_issue()],
    ):
        result = runner.invoke(
            app,
            ["check", "--path", str(tmp_path), "--format", "sarif"],
        )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["version"] == "2.1.0"


def test_check_format_jsonl_clean_exit_0(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    with patch("repolens.diagnostics.collect_fast_issues", return_value=[]):
        result = runner.invoke(
            app,
            ["check", "--path", str(tmp_path), "--format", "jsonl"],
        )
    assert result.exit_code == 0, result.output


def test_graph_cycles_and_would_cycle() -> None:
    result = runner.invoke(
        app,
        ["graph", "cycles", "--path", str(CYCLE_PKG), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["cyclicity"] >= 1
    assert payload["cycles"]

    edges = runner.invoke(app, ["graph", "edges", "--path", str(CYCLE_PKG)])
    assert edges.exit_code == 0, edges.output
    rows = json.loads(edges.stdout)
    assert rows

    deps = runner.invoke(
        app,
        ["graph", "deps", "packcycle.a", "--path", str(CYCLE_PKG), "--json"],
    )
    assert deps.exit_code == 0, deps.output

    cycle = runner.invoke(
        app,
        [
            "graph",
            "would-cycle",
            "--from",
            "packcycle.a",
            "--to",
            "packcycle.b",
            "--path",
            str(CYCLE_PKG),
        ],
    )
    assert cycle.exit_code in {0, 1}


def test_journal_cli_json(tmp_path: Path) -> None:
    from repolens.pipeline.journal import append_event

    append_event(
        tmp_path, "pass_completed", label="P1 Security", chars_in=10, chars_out=2
    )
    result = runner.invoke(app, ["journal", "--path", str(tmp_path), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["chars_in"] == 10
    assert payload["last_finished"] == "P1 Security"


def test_journal_cli_human(tmp_path: Path) -> None:
    from repolens.pipeline.journal import append_event

    append_event(
        tmp_path, "pass_completed", label="P1 Security", chars_in=10, chars_out=2
    )
    result = runner.invoke(app, ["journal", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "chars_in" in result.output
    assert "Honesty metric" in result.output


def test_journal_cli_empty(tmp_path: Path) -> None:
    result = runner.invoke(app, ["journal", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "No journal" in result.output


def test_collect_fast_issues_on_tiny_python(tmp_path: Path) -> None:
    from repolens.config import load_config
    from repolens.diagnostics import collect_fast_issues

    pkg = tmp_path / "tiny"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "a.py").write_text("x = 1\n", encoding="utf-8")
    issues = collect_fast_issues(pkg, load_config(pkg))
    assert isinstance(issues, list)
    cycle_issues = collect_fast_issues(CYCLE_PKG, load_config(CYCLE_PKG))
    assert any(i.category == "arch.import_cycle" for i in cycle_issues)


def test_graph_deps_text_and_dependents() -> None:
    text = runner.invoke(
        app, ["graph", "deps", "packcycle.a", "--path", str(CYCLE_PKG)]
    )
    assert text.exit_code == 0, text.output
    deps = runner.invoke(
        app, ["graph", "dependents", "packcycle.a", "--path", str(CYCLE_PKG), "--json"]
    )
    assert deps.exit_code == 0, deps.output
    json.loads(deps.stdout)


def test_graph_invalid_format_and_missing_graph(tmp_path: Path) -> None:
    bad = runner.invoke(
        app, ["graph", "cycles", "--path", str(CYCLE_PKG), "--format", "xml"]
    )
    assert bad.exit_code == 2
    missing = runner.invoke(app, ["graph", "deps", "nope", "--path", str(tmp_path)])
    assert missing.exit_code == 3


def test_ignore_add_and_list(tmp_path: Path) -> None:
    add = runner.invoke(
        app,
        [
            "ignore",
            "add",
            "--path",
            str(tmp_path),
            "--file",
            "src/a.py",
            "--category",
            "arch.import_cycle",
            "--reason",
            "wont_fix",
        ],
    )
    assert add.exit_code == 0, add.output
    listed = runner.invoke(app, ["ignore", "list", "--path", str(tmp_path)])
    assert listed.exit_code == 0, listed.output
    assert "arch.import_cycle" in listed.output


def test_duplicates_json_empty_tree(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["duplicates", "--path", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == []
