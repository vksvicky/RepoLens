"""Quality scorecard aggregation and Markdown rendering."""

from __future__ import annotations

from repolens.quality import (
    DEEP_NESTING_CATEGORY,
    MEGA_FILE_CATEGORY,
    NEAR_CLONE_CATEGORY,
    build_quality_scorecard,
    build_quality_scorecard_from_issues,
)
from repolens.report import render_markdown
from repolens.schema import FindingReport, Issue, QualityScorecard, Severity, Summary


def _issue(category: str, *, file: str = "a.py") -> Issue:
    return Issue(
        severity=Severity.LOW,
        priority="P3",
        category=category,
        file=file,
        line=1,
        title="t",
        explanation="e",
        recommendedFix="f",
        source="heuristic",
    )


def test_build_quality_scorecard_counts_categories_exactly() -> None:
    issues = [
        _issue(MEGA_FILE_CATEGORY, file="big.py"),
        _issue(MEGA_FILE_CATEGORY, file="huge.py"),
        _issue(DEEP_NESTING_CATEGORY, file="nest.py"),
        _issue(NEAR_CLONE_CATEGORY, file="clone_a.py"),
    ]
    card = build_quality_scorecard_from_issues(
        issues,
        near_clone_clusters=12,
        near_clone_occurrences=40,
        files_scanned=1840,
        notes=["40 additional clone clusters omitted from findings"],
    )
    assert card.megaFileCount == 2
    assert card.deepNestingCount == 1
    assert card.nearCloneClusters == 12
    assert card.nearCloneOccurrences == 40
    assert card.nearCloneFindingsEmitted == 1
    assert card.filesScanned == 1840
    assert card.notes == ["40 additional clone clusters omitted from findings"]


def test_build_quality_scorecard_low_level_fields() -> None:
    card = build_quality_scorecard(
        mega=3,
        nesting=7,
        near_clusters=12,
        near_occurrences=40,
        findings_emitted=10,
        files_scanned=1840,
        notes=[],
    )
    assert card == QualityScorecard(
        megaFileCount=3,
        deepNestingCount=7,
        nearCloneClusters=12,
        nearCloneOccurrences=40,
        nearCloneFindingsEmitted=10,
        filesScanned=1840,
        notes=[],
    )


def test_render_markdown_includes_quality_scorecard_section() -> None:
    report = FindingReport(
        confidence=80,
        summary=Summary(),
        issues=[],
        quality=QualityScorecard(
            megaFileCount=3,
            deepNestingCount=7,
            nearCloneClusters=12,
            nearCloneOccurrences=40,
            nearCloneFindingsEmitted=10,
            filesScanned=1840,
            notes=["40 additional clone clusters omitted from findings"],
        ),
    )
    md = render_markdown(
        report,
        mode="full",
        commit_go="go",
        push_go="go",
    )
    assert "## Quality scorecard (Fast Brain)" in md
    assert "| Mega-files | 3 |" in md
    assert "| Deep nesting | 7 |" in md
    assert "| Near-clone clusters | 12 |" in md
    assert "| Files scanned | 1840 |" in md
    assert "_40 additional clone clusters omitted from findings._" in md
    assert "Deterministic DRY/KISS signals" in md


def test_render_markdown_omits_section_when_quality_missing() -> None:
    report = FindingReport(confidence=80, summary=Summary(), issues=[])
    md = render_markdown(
        report,
        mode="full",
        commit_go="go",
        push_go="go",
    )
    assert "Quality scorecard" not in md
