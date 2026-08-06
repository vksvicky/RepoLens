"""Suppressed findings appear in Markdown audit section, not fail-on."""

from __future__ import annotations

from pathlib import Path

from repolens.report import render_markdown
from repolens.schema import FindingReport, Issue, Severity, Summary, SuppressedIssue
from repolens.suppressions import apply_suppressions
from repolens.triage import fail_on_triggered


def test_markdown_lists_suppressed() -> None:
    issue = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="sec.demo",
        file="a.py",
        line=1,
        title="Noise",
        explanation="x",
        recommendedFix="n/a",
        stableId="11111111-1111-4111-8111-111111111111",
        source="llm",
    )
    report = FindingReport(
        confidence=80,
        summary=Summary(),
        issues=[],
        suppressedIssues=[
            SuppressedIssue(
                issue=issue,
                reason="false_positive",
                mechanism="ignore_file",
                note="fixture",
            )
        ],
    )
    md = render_markdown(report, mode="review", commit_go="go", push_go="no-go")
    assert "## Suppressed" in md
    assert "false_positive" in md
    assert "Noise" in md


def test_fail_on_ignores_suppressed_active_only(tmp_path: Path) -> None:
    (tmp_path / ".repolens-ignore").write_text(
        """
[[ignore]]
stableId = "11111111-1111-4111-8111-111111111111"
reason = "wont_fix"
""",
        encoding="utf-8",
    )
    high = Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="sec.demo",
        file="a.py",
        line=1,
        title="Real",
        explanation="x",
        impact="Attacker may exploit this.",
        recommendedFix="fix",
        codeExample="return safe()",
        stableId="11111111-1111-4111-8111-111111111111",
        source="scanner",
    )
    active, suppressed = apply_suppressions(tmp_path, [high])
    report = FindingReport(
        confidence=70,
        summary=Summary(),
        issues=active,
        suppressedIssues=suppressed,
    )
    report.summary = report.recount_summary()
    assert not fail_on_triggered(report, "HIGH", scanner_only=True)
    assert len(suppressed) == 1
