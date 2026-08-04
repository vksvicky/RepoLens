"""Priority / band coercion (Phase 5.1)."""

from __future__ import annotations

from repolens.bands import coerce_issue_bands
from repolens.schema import Issue, Severity


def _issue(
    *,
    priority: str = "P1",
    category: str = "test",
    title: str = "Finding",
    severity: Severity = Severity.MEDIUM,
) -> Issue:
    high = severity in {Severity.CRITICAL, Severity.HIGH}
    return Issue(
        severity=severity,
        priority=priority,  # type: ignore[arg-type]
        category=category,
        file="a.py",
        line=1,
        title=title,
        explanation="test explanation",
        impact="impact" if high else "",
        recommendedFix="fix it",
        codeExample="example" if high else "",
    )


def test_heuristic_p1_coerced_to_p2() -> None:
    issues = [
        _issue(priority="P1", category="heuristic.mega_file", title="Mega file"),
    ]
    out = coerce_issue_bands(issues)
    assert len(out) == 1
    assert out[0].priority == "P2"
    assert out[0].category == "heuristic.mega_file"


def test_heuristic_p2_and_p3_unchanged() -> None:
    issues = [
        _issue(priority="P2", category="heuristic.ci_gaps"),
        _issue(priority="P3", category="heuristic.todo_density"),
    ]
    out = coerce_issue_bands(issues)
    assert [i.priority for i in out] == ["P2", "P3"]


def test_sec_practice_review_p1_stays() -> None:
    """True sec.* P1 findings are left alone (including practice_review)."""
    issues = [
        _issue(
            priority="P1",
            category="sec.practice_review",
            title="Weak auth practice",
            severity=Severity.HIGH,
        ),
    ]
    out = coerce_issue_bands(issues)
    assert out[0].priority == "P1"


def test_non_security_p1_coerced_to_p2() -> None:
    issues = [
        _issue(priority="P1", category="arch.structure", title="Layering smell"),
        _issue(priority="P1", category="rel.edge_cases", title="Missing boundary"),
        _issue(priority="P1", category="style.comment", title="Comment noise"),
    ]
    out = coerce_issue_bands(issues)
    assert all(i.priority == "P2" for i in out)


def test_scanner_categories_p1_stay() -> None:
    for category in (
        "gitleaks",
        "semgrep",
        "osv",
        "scanner.gitleaks",
        "tool.semgrep.rule",
        "deps.osv.vuln",
    ):
        out = coerce_issue_bands(
            [_issue(priority="P1", category=category, severity=Severity.HIGH)]
        )
        assert out[0].priority == "P1", category


def test_security_prefix_p1_stays() -> None:
    out = coerce_issue_bands(
        [_issue(priority="P1", category="security.injection", severity=Severity.HIGH)]
    )
    assert out[0].priority == "P1"


def test_sec_prefix_p1_stays() -> None:
    out = coerce_issue_bands(
        [_issue(priority="P1", category="sec.injection", severity=Severity.HIGH)]
    )
    assert out[0].priority == "P1"


def test_does_not_mutate_input() -> None:
    original = _issue(priority="P1", category="heuristic.mega_file")
    coerce_issue_bands([original])
    assert original.priority == "P1"
