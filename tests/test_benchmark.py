"""Phase 6.6: supporting actionability metrics from FindingReport JSON."""

from __future__ import annotations

from repolens.benchmark import score_actionability
from repolens.schema import FindingReport, Issue, Severity, Summary


def _issue(
    *,
    severity: Severity,
    code_example: str = "# fix",
    title: str = "demo",
    source: str | None = None,
) -> Issue:
    kwargs: dict = dict(
        severity=severity,
        priority="P1" if severity in {Severity.CRITICAL, Severity.HIGH} else "P2",
        category="sec.demo",
        file="a.py",
        line=1,
        title=title,
        explanation="x",
        recommendedFix="Fix it",
        codeExample=code_example,
        source=source,
    )
    if severity in {Severity.CRITICAL, Severity.HIGH}:
        kwargs["impact"] = "Attacker may exploit this in production."
        if not str(kwargs["codeExample"]).strip():
            kwargs["codeExample"] = "# placeholder"
    return Issue(**kwargs)


def test_score_actionability_counts_examples() -> None:
    report = FindingReport(
        confidence=70,
        summary=Summary(high=1, medium=1, low=1),
        issues=[
            _issue(severity=Severity.HIGH, code_example="return safe()", source="llm"),
            _issue(severity=Severity.LOW, code_example="", title="noise", source="scanner"),
            _issue(severity=Severity.MEDIUM, code_example="ok", source="heuristic"),
        ],
    )
    scores = score_actionability(report)
    assert scores.total_issues == 3
    assert scores.critical_high == 1
    assert scores.critical_high_with_code_example == 1
    assert scores.medium_low == 2
    assert scores.medium_low_with_code_example == 1
    assert scores.issues_with_code_example == 2
    assert scores.suggested_fix_readiness == 2 / 3
    assert scores.llm_sourced == 1
    assert scores.scanner_sourced == 1
    assert scores.heuristic_sourced == 1


def test_score_actionability_empty_report() -> None:
    report = FindingReport(confidence=80, summary=Summary(), issues=[])
    scores = score_actionability(report)
    assert scores.total_issues == 0
    assert scores.suggested_fix_readiness is None
    assert scores.issues_with_code_example == 0
