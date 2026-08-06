"""Explain command: resolve UUID and write deep-dive artifact."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from repolens.cli import app
from repolens.explain import (
    ExplainDisabledError,
    ExplainSolution,
    IssueNotFoundError,
    _evidence_bundle,
    _safe_issue_path,
    build_diagram_from_moves,
    build_recommended_next_step,
    dedupe_solutions,
    find_issue,
    import_diff_risk_notes,
    load_latest_report,
    next_step_is_vague,
    parse_move,
    run_explain,
    sanitize_explain_mermaid,
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


def test_safe_issue_path_blocks_traversal(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text("print(1)\n", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP_SECRET\n", encoding="utf-8")
    assert _safe_issue_path(root, "app.py") == (root / "app.py").resolve()
    assert _safe_issue_path(root, "../secret.txt") is None
    assert _safe_issue_path(root, str(secret)) is None
    issue = Issue(
        severity=Severity.LOW,
        priority="P3",
        category="heuristic.mega_file",
        file="../secret.txt",
        line=1,
        title="x",
        explanation="x",
        impact="",
        recommendedFix="",
        codeExample="",
    )
    outline, excerpt = _evidence_bundle(root, issue)
    assert "TOP_SECRET" not in outline
    assert "TOP_SECRET" not in excerpt


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
            "problem": "SQL built from user input in the login handler.",
            "impact": "Attacker can read the database.",
            "solutions": [
                {
                    "title": "Parameterise execute()",
                    "tradeoffs": "Small refactor",
                    "impactEffort": "High impact, low effort",
                    "moves": ["login_query (lines 10–20) stays; bind params"],
                    "importDiff": "- q = f\"SELECT * FROM u WHERE id={uid}\"\n"
                    "+ cursor.execute(\"SELECT * FROM u WHERE id=%s\", (uid,))",
                },
                {"title": "ORM", "tradeoffs": "Larger change"},
            ],
            "proposedRefactorDiff": "+ # use bound parameters\n",
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
    assert "Actionable solutions" in text
    assert "Diagram" in text
    assert "Parameterise" in text
    assert "Fingerprint" in text
    assert "Proposed refactor" in text


def test_recommended_next_step_expands_vague_llm_line() -> None:
    vague = (
        "Refactor `commands_review.py` into separate modules for each "
        "command and update import statements accordingly."
    )
    assert next_step_is_vague(
        vague,
        ["_run_mode (lines 17–191) → run_mode.py"],
    )
    text = build_recommended_next_step(
        next_step=vague,
        host_file="src/repolens/cli/commands_review.py",
        plan_title="Split by Functionality",
        moves=[
            "_run_mode (lines 17–191) → run_mode.py",
            "review (lines 195–327) → review_command.py",
        ],
    )
    assert "Extract `_run_mode`" in text
    assert "run_mode.py" in text
    assert "review_command.py" in text
    assert "thin shell" in text
    assert "vague" not in text.lower()
    assert vague not in text  # replaced, not echoed alone


def test_parse_move_and_diagram_match_explain_plan() -> None:
    assert parse_move("_run_mode (lines 17–191) → run_mode.py") == (
        "_run_mode",
        "run_mode.py",
    )
    block = build_diagram_from_moves(
        host_file="src/repolens/cli/commands_review.py",
        moves=[
            "_run_mode (lines 17–191) → run_mode.py",
            "review (lines 195–327) → review_command.py",
            "sentinel (lines 331–450) → sentinel_command.py",
            "architecture (lines 454–573) → architecture_command.py",
        ],
        plan_title="Split by Functionality",
    )
    assert "commands_review---run_mode" in block
    assert "-->" not in block.split("```mermaid", 1)[-1]
    assert "extract `_run_mode`" in block
    assert "`_run_mode`" in block
    assert "review_command.py" in block
    # ASCII (meaning) must appear before Mermaid (topology-only).
    assert block.index("extract `_run_mode`") < block.index("```mermaid")
    assert "same moves as solution" in block.lower() or "Split by Functionality" in block


def test_sanitize_explain_mermaid_quotes_dotted_filenames() -> None:
    raw = (
        "flowchart TD\n"
        "    commands_review.py --> run_mode.py\n"
        "    commands_review.py --> review_command.py\n"
    )
    fixed = sanitize_explain_mermaid(raw)
    assert "commands_review_py---run_mode_py" in fixed
    assert "commands_review_py---review_command_py" in fixed
    assert "-->" not in fixed
    assert " --> " not in fixed


def test_dedupe_solutions_collapses_identical_moves() -> None:
    a = ExplainSolution(
        title="Split A",
        moves=["review → review_command.py", "sentinel → sentinel_command.py"],
    )
    b = ExplainSolution(
        title="Split B (same plan)",
        moves=["review → review_command.py", "sentinel → sentinel_command.py"],
    )
    c = ExplainSolution(title="Other", moves=["_run_mode → run_mode.py"])
    out = dedupe_solutions([a, b, c])
    assert len(out) == 2
    assert out[0].title == "Split A"
    assert out[1].title == "Other"


def test_import_diff_risk_notes_flags_typer_removal() -> None:
    diff = (
        "--- a/x.py\n+++ b/x.py\n"
        "-import typer\n"
        "-from pathlib import Path\n"
        "+from .review_command import review\n"
    )
    notes = import_diff_risk_notes(diff)
    assert notes
    assert "typer" in notes[0]


def test_generic_boilerplate_falls_back_to_outline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    root = tmp_path / "proj"
    root.mkdir()
    out = root / "reports"
    out.mkdir()
    src = root / "commands_review.py"
    src.write_text(
        "def review():\n" + ("    pass\n" * 100) + "\ndef sentinel():\n" + ("    pass\n" * 80),
        encoding="utf-8",
    )
    run_id = "11111111-1111-4111-8111-111111111111"
    stable_id = "22222222-2222-4222-8222-222222222222"
    issue = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="heuristic.mega_file",
        file="commands_review.py",
        line=1,
        title="Mega-file",
        explanation="Too big",
        impact="",
        recommendedFix="Split",
        codeExample="# n/a",
        stableId=stable_id,
        runId=run_id,
        source="heuristic",
    )
    report = FindingReport(
        confidence=70, summary=Summary(medium=1), issues=[issue]
    )
    path = out / "gate_review_report_review_2026-08-06_1000.json"
    path.write_text(report.model_dump_json(), encoding="utf-8")
    write_last_report_pointer(root, path)

    waffle = json.dumps(
        {
            "problem": "Mega-file",
            "impact": "Hard to review",
            "solutions": [
                {"title": "Split by Responsibility", "tradeoffs": "planning"},
                {"title": "Modularize Functions", "tradeoffs": "files"},
                {"title": "Use Classes for Grouping", "tradeoffs": "complexity"},
            ],
            "diagramMermaid": "flowchart LR\n  A --> B[UI_module.py]",
            "nextStep": "Evaluate structure",
        }
    )
    with patch("repolens.explain.analyze_raw", return_value=waffle):
        artifact = run_explain(
            uuid=run_id, project_root=root, out_dir=out, render_image="never"
        )
    text = artifact.read_text(encoding="utf-8")
    assert "Structure used as evidence" in text
    assert "review" in text
    assert "UI_module" not in text


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
