"""Phase 6.9: near-duplicate finding clustering."""

from __future__ import annotations

from repolens.cluster import cluster_near_duplicates
from repolens.schema import Issue, Severity


def _issue(
    *,
    severity: Severity,
    title: str,
    file: str = "a.py",
    category: str = "sec.injection",
) -> Issue:
    kwargs: dict = dict(
        severity=severity,
        priority="P1" if severity in {Severity.CRITICAL, Severity.HIGH} else "P2",
        category=category,
        file=file,
        line=1,
        title=title,
        explanation="x",
        recommendedFix="fix",
        source="llm",
    )
    if severity in {Severity.CRITICAL, Severity.HIGH}:
        kwargs["impact"] = "Attacker may exploit this."
        kwargs["codeExample"] = "return safe()"
    return Issue(**kwargs)


def test_cluster_keeps_highest_severity() -> None:
    issues = [
        _issue(severity=Severity.MEDIUM, title="Command injection in foo"),
        _issue(severity=Severity.HIGH, title="Command injection in foo"),
        _issue(severity=Severity.LOW, title="Unrelated", category="rel.bugs"),
    ]
    out = cluster_near_duplicates(issues)
    assert len(out) == 2
    high = next(i for i in out if i.category == "sec.injection")
    assert high.severity == Severity.HIGH
    assert high.clusteredCount == 2


def test_cluster_different_files_kept() -> None:
    issues = [
        _issue(severity=Severity.HIGH, title="Same title", file="a.py"),
        _issue(severity=Severity.HIGH, title="Same title", file="b.py"),
    ]
    out = cluster_near_duplicates(issues)
    assert len(out) == 2
