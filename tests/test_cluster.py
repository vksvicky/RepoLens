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


def test_clusters_heuristic_and_llm_gitignore_twins():
    a = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="heuristic.gitignore_secrets",
        file=".gitignore",
        line=1,
        title="Gitignore missing .env",
        explanation="x",
        impact="y",
        recommendedFix="z",
        codeExample="#",
        source="heuristic",
    )
    b = Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="sec.repo_hygiene_secrets",
        file=".gitignore",
        line=1,
        title="Gitignore Missing .env / Secret Patterns",
        explanation="x",
        impact="y",
        recommendedFix="z",
        codeExample="#",
        source="llm",
    )
    out = cluster_near_duplicates([a, b])
    assert len(out) == 1
    assert out[0].severity == Severity.HIGH
    assert out[0].source == "llm"  # higher severity wins
    assert out[0].clusteredCount == 2


def test_cluster_tie_prefers_llm_text_over_heuristic():
    """Same severity: keep LLM row (rich text), not generic heuristic stub."""
    heur = Issue(
        severity=Severity.MEDIUM,
        priority="P3",
        category="heuristic.mega_file",
        file="src/big.py",
        line=1,
        title="Mega-file detected",
        explanation="File is large.",
        impact="Harder to review.",
        recommendedFix="Split it.",
        codeExample="# n/a",
        source="heuristic",
    )
    llm = Issue(
        severity=Severity.MEDIUM,
        priority="P3",
        category="arch.structure_size",
        file="src/big.py",
        line=1,
        title="Mega-file: big.py has 637 lines",
        explanation="The `_run_mode` function is 175 lines; split by command.",
        impact="Merge conflicts and review fatigue.",
        recommendedFix="Extract `_run_mode` into run_mode.py.",
        codeExample="+ from .run_mode import _run_mode",
        source="llm",
    )
    out = cluster_near_duplicates([heur, llm])
    assert len(out) == 1
    assert out[0].source == "llm"
    assert "_run_mode" in out[0].explanation
    assert out[0].clusteredCount == 2


def test_unmapped_category_same_file_different_titles_not_collapsed() -> None:
    """Unmapped categories must not collapse solely on file + category."""
    issues = [
        _issue(
            severity=Severity.HIGH,
            title="SQL injection in query builder",
            file="db.py",
            category="sec.injection",
        ),
        _issue(
            severity=Severity.HIGH,
            title="Command injection in shell wrapper",
            file="db.py",
            category="sec.injection",
        ),
    ]
    out = cluster_near_duplicates(issues)
    assert len(out) == 2


def test_cluster_tie_prefers_scanner_over_llm() -> None:
    """Equal severity twin: scanner outranks llm."""
    scanner = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="heuristic.gitignore_secrets",
        file=".gitignore",
        line=1,
        title="Gitignore missing .env",
        explanation="scanner finding",
        impact="Secrets may leak.",
        recommendedFix="Add .env",
        codeExample="#",
        source="scanner",
    )
    llm = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="sec.repo_hygiene_secrets",
        file=".gitignore",
        line=1,
        title="Gitignore Missing .env / Secret Patterns",
        explanation="llm finding",
        impact="Secrets may leak.",
        recommendedFix="Add .env",
        codeExample="#",
        source="llm",
    )
    out = cluster_near_duplicates([llm, scanner])
    assert len(out) == 1
    assert out[0].source == "scanner"
    assert out[0].clusteredCount == 2
