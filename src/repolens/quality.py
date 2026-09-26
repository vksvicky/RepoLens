"""Fast Brain quality scorecard (mega-files, nesting, near-clones)."""

from __future__ import annotations

from collections.abc import Sequence

from repolens.schema import Issue, QualityScorecard

# Must match find_mega_files / find_deep_nesting / find_near_clones issue categories.
MEGA_FILE_CATEGORY = "heuristic.mega_file"
DEEP_NESTING_CATEGORY = "heuristic.deep_nesting"
NEAR_CLONE_CATEGORY = "quality.near_clone"


def _count_categories(issues: Sequence[Issue]) -> tuple[int, int, int]:
    mega = nesting = near = 0
    for issue in issues:
        if issue.category == MEGA_FILE_CATEGORY:
            mega += 1
        elif issue.category == DEEP_NESTING_CATEGORY:
            nesting += 1
        elif issue.category == NEAR_CLONE_CATEGORY:
            near += 1
    return mega, nesting, near


def build_quality_scorecard(
    *,
    mega: int,
    nesting: int,
    near_clusters: int,
    near_occurrences: int,
    findings_emitted: int,
    files_scanned: int,
    notes: list[str] | None = None,
) -> QualityScorecard:
    return QualityScorecard(
        megaFileCount=mega,
        deepNestingCount=nesting,
        nearCloneClusters=near_clusters,
        nearCloneOccurrences=near_occurrences,
        nearCloneFindingsEmitted=findings_emitted,
        filesScanned=files_scanned,
        notes=list(notes or []),
    )


def build_quality_scorecard_from_issues(
    issues: Sequence[Issue],
    *,
    near_clone_clusters: int,
    near_clone_occurrences: int,
    files_scanned: int,
    notes: list[str] | None = None,
) -> QualityScorecard:
    mega, nesting, near_findings = _count_categories(issues)
    return build_quality_scorecard(
        mega=mega,
        nesting=nesting,
        near_clusters=near_clone_clusters,
        near_occurrences=near_clone_occurrences,
        findings_emitted=near_findings,
        files_scanned=files_scanned,
        notes=notes,
    )
