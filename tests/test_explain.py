"""Explain command: resolve UUID and write deep-dive artifact."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from repolens.cli import app
from repolens.explain import (
    ExplainDisabledError,
    IssueNotFoundError,
    find_issue,
    load_latest_report,
    run_explain,
    write_last_report_pointer,
)
from repolens.schema import FindingReport, Issue, Severity, Summary

runner = CliRunner()


def _report_with_issue(*, run_id: str, stable_id: str) -> FindingReport:
    issue = Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="sec.injection",
        file="app.py",
        line=10,
        title="SQL injection",
        explanation="User input in query.",
        impact="Data breach.",
        recommendedFix="Use parameterised queries.",
        codeExample="cursor.execute(sql, (user,))",
        stableId=stable_id,
        runId=run_id,
    )
    return FindingReport(
        confidence=70,
        summary=Summary(high=1),
        issues=[issue],
    )


def test_find_issue_prefers_run_id() -> None:
    report = _report_with_issue(
        run_id="11111111-1111-4111-8111-111111111111",
        stable_id="22222222-2222-4222-8222-222222222222",
    )
    found = find_issue(report, "11111111-1111-4111-8111-111111111111")
    assert found.title == "SQL injection"


def test_find_issue_falls_back_to_stable_id() -> None:
    report = _report_with_issue(
        run_id="11111111-1111-4111-8111-111111111111",
        stable_id="22222222-2222-4222-8222-222222222222",
    )
    found = find_issue(report, "22222222-2222-4222-8222-222222222222")
    assert found.runId == "11111111-1111-4111-8111-111111111111"


def test_load_latest_report_uses_pointer(tmp_path: Path) -> None:
    out = tmp_path / "reports"
    out.mkdir()
    report = _report_with_issue(
        run_id="11111111-1111-4111-8111-111111111111",
        stable_id="22222222-2222-4222-8222-222222222222",
    )
    path = out / "gate_review_report_review_2026-08-06_1000.json"
    path.write_text(report.model_dump_json(), encoding="utf-8")
    write_last_report_pointer(tmp_path, path)
    loaded, loaded_path = load_latest_report(tmp_path, out_dir=out)
    assert loaded_path == path
    assert loaded.issues[0].runId == "11111111-1111-4111-8111-111111111111"


def test_run_explain_writes_markdown(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    root = tmp_path / "proj"
    root.mkdir()
    out = root / "reports"
    out.mkdir()
    run_id = "11111111-1111-4111-8111-111111111111"
    stable_id = "22222222-2222-4222-8222-222222222222"
    report = _report_with_issue(run_id=run_id, stable_id=stable_id)
    path = out / "gate_review_report_review_2026-08-06_1000.json"
    path.write_text(report.model_dump_json(), encoding="utf-8")
    write_last_report_pointer(root, path)

    llm_json = json.dumps(
        {
            "problem": "SQL built from user input.",
            "impact": "Attacker can read the database.",
            "solutions": [
                {"title": "Parameterise", "tradeoffs": "Small refactor"},
                {"title": "ORM", "tradeoffs": "Larger change"},
            ],
            "diagramMermaid": "flowchart LR\n  A[Input] --> B[Query]",
            "nextStep": "Parameterise the login query first.",
        }
    )

    with patch("repolens.explain.analyze_raw", return_value=llm_json):
        artifact = run_explain(
            uuid=run_id,
            project_root=root,
            out_dir=out,
            diagram=True,
            render_image="never",
        )
    text = artifact.read_text(encoding="utf-8")
    assert "Problem" in text
    assert "Solutions" in text
    assert "Diagram" in text
    assert "Parameterise" in text


def test_explain_disabled_raises(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    (tmp_path / "xdg" / "repolens").mkdir(parents=True)
    (tmp_path / "xdg" / "repolens" / "config.toml").write_text(
        "[explain]\nenabled = false\n",
        encoding="utf-8",
    )
    root = tmp_path / "proj"
    root.mkdir()
    out = root / "reports"
    out.mkdir()
    report = _report_with_issue(
        run_id="11111111-1111-4111-8111-111111111111",
        stable_id="22222222-2222-4222-8222-222222222222",
    )
    path = out / "gate_review_report_review_2026-08-06_1000.json"
    path.write_text(report.model_dump_json(), encoding="utf-8")
    write_last_report_pointer(root, path)
    try:
        run_explain(
            uuid="11111111-1111-4111-8111-111111111111",
            project_root=root,
            out_dir=out,
        )
        raise AssertionError("expected ExplainDisabledError")
    except ExplainDisabledError:
        pass


def test_cli_explain_missing_uuid_exit_2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    root = tmp_path / "proj"
    root.mkdir()
    out = root / "reports"
    out.mkdir()
    report = _report_with_issue(
        run_id="11111111-1111-4111-8111-111111111111",
        stable_id="22222222-2222-4222-8222-222222222222",
    )
    path = out / "gate_review_report_review_2026-08-06_1000.json"
    path.write_text(report.model_dump_json(), encoding="utf-8")
    write_last_report_pointer(root, path)
    result = runner.invoke(
        app,
        [
            "explain",
            "99999999-9999-4999-8999-999999999999",
            "--path",
            str(root),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 2
    assert "not found" in result.output.lower()
