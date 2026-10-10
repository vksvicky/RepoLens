"""``repolens fix`` grounded patch apply (#109)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from repolens.cli import app
from repolens.fix_apply import (
    FixRefuseError,
    build_unified_diff,
    plan_fix,
)
from repolens.schema import FindingReport, Issue, Severity, Summary

runner = CliRunner()

BEFORE_AFTER = """\
# Before
if a == b:
    ok()

# After
if hmac.compare_digest(a, b):
    ok()
"""


def _hi(
    *,
    code: str,
    file: str = "src/app.py",
    stable: str = "fp-abc123",
) -> Issue:
    return Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="sec.x",
        file=file,
        line=3,
        title="Bad compare",
        explanation="timing",
        impact="forge",
        recommendedFix="use compare_digest",
        codeExample=code,
        stableId=stable,
    )


def test_plan_fix_before_after_builds_diff(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    target = root / "src" / "app.py"
    target.write_text("def f():\n    if a == b:\n        ok()\n", encoding="utf-8")
    issue = _hi(code=BEFORE_AFTER)
    plan = plan_fix(root, issue)
    assert plan.relative_path == "src/app.py"
    assert "hmac.compare_digest" in plan.new_text
    diff = build_unified_diff(plan)
    assert diff.startswith("--- ")
    assert "hmac.compare_digest" in diff


def test_plan_fix_refuses_empty_example(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("x=1\n", encoding="utf-8")
    issue = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="rel.x",
        file="src/app.py",
        line=1,
        title="t",
        explanation="e",
        recommendedFix="fix",
        codeExample="",
        stableId="fp-empty",
    )
    with pytest.raises(FixRefuseError, match="grounded|codeExample"):
        plan_fix(root, issue)


def test_plan_fix_refuses_missing_file(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(FixRefuseError, match="file"):
        plan_fix(root, _hi(code=BEFORE_AFTER, file="missing.py"))


def test_plan_fix_refuses_multi_file_hint(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("if a == b:\n    ok()\n", encoding="utf-8")
    code = BEFORE_AFTER + "\nAlso edit src/other.py and pkg/mod.py\n"
    with pytest.raises(FixRefuseError, match="multi-file|single file"):
        plan_fix(root, _hi(code=code))


def test_cli_fix_patch_stdout(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text(
        "def f():\n    if a == b:\n        ok()\n", encoding="utf-8"
    )
    reports = root / "reports"
    reports.mkdir()
    report = FindingReport(
        confidence=80,
        summary=Summary(high=1),
        issues=[_hi(code=BEFORE_AFTER)],
    )
    (reports / "gate_review_report_review_2026-10-10_0900.json").write_text(
        report.model_dump_json(), encoding="utf-8"
    )
    result = runner.invoke(
        app,
        [
            "fix", "fp-abc123", "--path", str(root), "--out", str(reports),
            "--patch",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "hmac.compare_digest" in result.output
    assert "hmac.compare_digest" not in (root / "src" / "app.py").read_text(
        encoding="utf-8"
    )


def test_cli_fix_interactive_applies_and_ast_checks(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    target = root / "src" / "app.py"
    target.write_text("def f():\n    if a == b:\n        ok()\n", encoding="utf-8")
    reports = root / "reports"
    reports.mkdir()
    report = FindingReport(
        confidence=80,
        summary=Summary(high=1),
        issues=[_hi(code=BEFORE_AFTER)],
    )
    (reports / "gate_review_report_review_2026-10-10_0900.json").write_text(
        report.model_dump_json(), encoding="utf-8"
    )
    result = runner.invoke(
        app,
        [
            "fix", "fp-abc123", "--path", str(root), "--out", str(reports),
            "--interactive", "--yes",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "hmac.compare_digest" in target.read_text(encoding="utf-8")
