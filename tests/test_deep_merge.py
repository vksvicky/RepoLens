"""Deep-pass merge behaviour.

Kept apart from ``test_deep.py`` so that file stays under the mega-file limit.
"""

from __future__ import annotations

from types import SimpleNamespace

from repolens.deep import merge_reports
from repolens.schema import FindingReport, Issue, Summary


def _issue(
    *,
    file: str = "a.py",
    title: str = "Finding",
    severity: str = "LOW",
    priority: str = "P3",
) -> Issue:
    return Issue.model_validate(
        {
            "severity": severity,
            "priority": priority,
            "category": "Test",
            "file": file,
            "line": 1,
            "title": title,
            "explanation": "x",
            "impact": "impact text" if severity in {"CRITICAL", "HIGH"} else "",
            "recommendedFix": "fix it",
            "codeExample": "code()" if severity in {"CRITICAL", "HIGH"} else "",
            "fixTiming": "before launch",
        }
    )


def _report(
    *,
    confidence: int,
    issues: list[Issue] | None = None,
    gaps: list[str] | None = None,
) -> FindingReport:
    issues = issues or []
    report = FindingReport(
        confidence=confidence,
        summary=Summary(),
        issues=issues,
        durabilityGaps=gaps or [],
    )
    report.summary = report.recount_summary()
    return report


def test_merge_reports_drops_model_restatements_of_measurements() -> None:
    """Fast Brain owns complexity and heuristics. Workflow YAML is not a test file."""
    measured = _issue(file=".gitignore", title="Gitignore missing secret patterns").model_copy(
        update={"category": "heuristic.gitignore_secrets", "source": "heuristic"}
    )
    model = _report(
        confidence=40,
        issues=[
            _issue(
                file="src/repolens/report_sections.py",
                title="complex provenance",
                severity="HIGH",
            ).model_copy(update={"category": "quality.complexity"}),
            _issue(
                file="src/repolens/heuristics/gitignore_secrets.py",
                title="Gitignore missing secret patterns",
            ).model_copy(
                update={
                    "category": "heuristic.gitignore_secrets",
                    "source": "heuristic",
                }
            ),
            _issue(
                file=".github/workflows/ci.yml", title="No unit tests for CI workflow"
            ).model_copy(update={"category": "arch.testing"}),
            _issue(
                file=".gitlab-ci.yml", title="No unit tests for GitLab CI"
            ).model_copy(update={"category": "arch.testing"}),
            _issue(
                file="Jenkinsfile", title="No unit tests for Jenkins"
            ).model_copy(update={"category": "testing.missing_tests"}),
            _issue(file=".gitignore", title="Potential secret leakage in .gitignore").model_copy(
                update={"category": "sec.repo_hygiene_secrets"}
            ),
            _issue(
                file="src/app.py", title="Hardcoded token in source"
            ).model_copy(update={"category": "sec.repo_hygiene_secrets"}),
            _issue(
                file="src/repolens/cli/export.py", title="Real reliability gap"
            ).model_copy(update={"category": "rel.error_recovery"}),
            _issue(
                file="tests/test_cli.py", title="Missing a branch test"
            ).model_copy(update={"category": "arch.testing"}),
        ],
    )

    merged = merge_reports([model], [measured])
    titles = [issue.title for issue in merged.issues]
    assert titles.count("Gitignore missing secret patterns") == 1
    assert "Real reliability gap" in titles
    assert "Missing a branch test" in titles
    assert "complex provenance" not in titles
    assert "No unit tests for CI workflow" not in titles
    assert "No unit tests for GitLab CI" not in titles
    assert "No unit tests for Jenkins" not in titles
    assert "Potential secret leakage in .gitignore" not in titles
    assert "Hardcoded token in source" in titles


def test_non_deep_merge_keeps_measured_complexity() -> None:

    from repolens.pipeline.run_finish import _merge_llm_report

    model_claim = _issue(
        file="src/repolens/report_sections.py",
        title="complex provenance",
        severity="HIGH",
    ).model_copy(update={"category": "quality.complexity"})
    measured = _issue(
        file="src/repolens/cli/export.py",
        title="High complexity: export",
        severity="HIGH",
    ).model_copy(update={"category": "quality.complexity", "source": "heuristic"})
    report = FindingReport(
        confidence=50,
        summary=Summary(),
        issues=[model_claim, _issue(file="a.py", title="Real gap")],
    )
    state = SimpleNamespace(
        use_deep=False,
        report=report,
        non_llm_issues=[measured],
        scanner_runs=[],
        scanner_gaps=[],
        triage_plan=None,
        store=None,
    )
    _merge_llm_report(state)
    titles = {issue.title for issue in state.report.issues}
    assert "complex provenance" not in titles
    assert "High complexity: export" in titles
    assert "Real gap" in titles


def test_merge_reports_dedupes_file_title_and_uses_min_confidence() -> None:
    shared = _issue(file="auth.py", title="Missing check", severity="MEDIUM")
    a = _report(
        confidence=80,
        issues=[shared, _issue(file="a.py", title="A only")],
        gaps=["gap-a"],
    )
    b = _report(
        confidence=55,
        issues=[
            _issue(file="auth.py", title="Missing check", severity="HIGH"),
            _issue(file="b.py", title="B only"),
        ],
        gaps=["gap-b", "gap-a"],
    )
    heuristic = [_issue(file="h.py", title="Heuristic")]
    merged = merge_reports([a, b], heuristic)

    titles = {(i.file, i.title) for i in merged.issues}
    assert ("auth.py", "Missing check") in titles
    dupes = [
        i
        for i in merged.issues
        if i.file == "auth.py" and i.title == "Missing check"
    ]
    assert len(dupes) == 1
    assert merged.confidence == 55
    assert "gap-a" in merged.durabilityGaps
    assert "gap-b" in merged.durabilityGaps
    assert any(i.file == "h.py" for i in merged.issues)
    assert merged.summary == merged.recount_summary()
    assert merged.summary.high == 0
    assert merged.summary.medium == 0
    assert merged.summary.low == 1
    assert all(issue.source == "llm" for issue in merged.issues if issue.file != "h.py")


def test_merge_reports_ignores_empty_parts_for_confidence() -> None:
    empty = _report(confidence=90, issues=[], gaps=[])
    solid = _report(confidence=40, issues=[_issue()], gaps=[])
    merged = merge_reports([empty, solid], [])
    assert merged.confidence == 40


def test_merge_reports_empty_parts_list_uses_heuristics() -> None:
    heuristic = [_issue(file="h.py", title="Only heuristic")]
    merged = merge_reports([], heuristic)
    assert len(merged.issues) == 1
    assert merged.confidence == 0
    assert merged.summary.low == 1


