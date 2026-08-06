"""Phase 6.8: PR job summary + workflow annotations."""

from __future__ import annotations

from pathlib import Path

from repolens.pr_summary import (
    find_newest_report_json,
    render_pr_summary,
    render_workflow_annotations,
)
from repolens.schema import FindingReport, Issue, Severity, Summary


def _issue(
    *,
    severity: Severity,
    title: str = "demo",
    file: str = "src/a.py",
    line: int = 10,
    code: str = "return safe()",
) -> Issue:
    kwargs: dict = dict(
        severity=severity,
        priority="P1" if severity in {Severity.CRITICAL, Severity.HIGH} else "P2",
        category="sec.demo",
        file=file,
        line=line,
        title=title,
        explanation="why",
        recommendedFix="Do the fix",
        codeExample=code,
        source="llm",
    )
    if severity in {Severity.CRITICAL, Severity.HIGH}:
        kwargs["impact"] = "Attacker may exploit this."
    return Issue(**kwargs)


def test_render_pr_summary_includes_critical_fix() -> None:
    report = FindingReport(
        confidence=70,
        summary=Summary(critical=1, medium=1),
        issues=[
            _issue(severity=Severity.CRITICAL, title="SQLi"),
            _issue(severity=Severity.MEDIUM, title="noise", code=""),
        ],
    )
    md = render_pr_summary(report)
    assert "## RepoLens PR summary" in md
    assert "Critical 1" in md
    assert "SQLi" in md
    assert "return safe()" in md
    assert "Do the fix" in md
    assert "noise" not in md  # Medium not in suggested-fix section


def test_workflow_annotations_critical_error_high_warning() -> None:
    report = FindingReport(
        confidence=70,
        summary=Summary(critical=1, high=1),
        issues=[
            _issue(severity=Severity.CRITICAL, title="A", file="a.py", line=3),
            _issue(severity=Severity.HIGH, title="B", file="b.py", line=7),
        ],
    )
    lines = render_workflow_annotations(report)
    assert any(l.startswith("::error ") and "file=a.py" in l and "line=3" in l for l in lines)
    assert any(l.startswith("::warning ") and "file=b.py" in l for l in lines)
    assert any("A" in l for l in lines)


def test_annotations_skip_path_escape() -> None:
    report = FindingReport(
        confidence=70,
        summary=Summary(critical=1),
        issues=[
            _issue(
                severity=Severity.CRITICAL,
                file="../outside.py",
                title="escape",
            )
        ],
    )
    lines = render_workflow_annotations(report)
    assert lines  # still emit annotation without file= or with title only
    assert all("../" not in l for l in lines)


def test_find_newest_report_json(tmp_path: Path) -> None:
    older = tmp_path / "gate_review_report_review_2026-01-01_1200.json"
    newer = tmp_path / "gate_review_report_review_2026-08-06_1500.json"
    sarif = tmp_path / "gate_review_report_review_2026-08-06_1501.sarif.json"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")
    sarif.write_text('{"version":"2.1.0"}', encoding="utf-8")
    assert find_newest_report_json(tmp_path) == newer
