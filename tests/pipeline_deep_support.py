"""Shared fixtures for deep-pipeline tests."""

from __future__ import annotations

from repolens.llm_structured import StructuredLlmResult
from repolens.schema import FindingReport, Issue, Severity, Summary


def _issue(
    *,
    file: str,
    title: str,
    priority: str = "P1",
    severity: Severity = Severity.LOW,
) -> Issue:
    return Issue(
        severity=severity,
        priority=priority,  # type: ignore[arg-type]
        category="test",
        file=file,
        line=1,
        title=title,
        explanation=f"Addresses checklist theme for {title}",
        impact="",
        recommendedFix="fix it",
        codeExample="",
    )


def _pass_report(
    *,
    title: str,
    file: str,
    priority: str,
    coverage_na: list[str],
) -> StructuredLlmResult:
    gaps = [f"coverage:{cid}: N/A — not applicable in fixture" for cid in coverage_na]
    report = FindingReport(
        confidence=70,
        summary=Summary(),
        issues=[_issue(file=file, title=title, priority=priority)],
        durabilityGaps=gaps,
    )
    report.summary = report.recount_summary()
    return StructuredLlmResult(
        report=report, raw_text="{}", layer="ok", error=None
    )
