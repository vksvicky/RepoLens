"""Merge, dedupe, and claim filters for deep pass reports."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from repolens.schema import FindingReport, Issue, Summary

_TESTING_CATEGORIES = frozenset(
    {"arch.testing", "testing.missing_tests", "testing.scenario_gap"}
)
_GITIGNORE_SECRET_CATEGORIES = frozenset(
    {"sec.repo_hygiene_secrets", "sec.secrets", "heuristic.gitignore_secrets"}
)
_CI_PIPELINE_NAMES = frozenset(
    {
        ".gitlab-ci.yml",
        ".gitlab-ci.yaml",
        "azure-pipelines.yml",
        "azure-pipelines.yaml",
        "bitbucket-pipelines.yml",
        ".travis.yml",
        "appveyor.yml",
        ".drone.yml",
        "woodpecker.yml",
    }
)


def _dedupe_issues(issues: Iterable[Issue]) -> list[Issue]:
    out: list[Issue] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        key = (issue.file, issue.title)
        if key in seen:
            continue
        seen.add(key)
        out.append(issue)
    return out


def _combine_gaps(parts: Sequence[FindingReport]) -> list[str]:
    gaps: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for gap in part.durabilityGaps:
            if gap in seen:
                continue
            seen.add(gap)
            gaps.append(gap)
    return gaps


def _min_confidence(parts: Sequence[FindingReport]) -> int:
    confidences = [
        part.confidence for part in parts if part.issues or part.durabilityGaps
    ]
    return min(confidences) if confidences else 0


def _normalise_repo_path(file: str) -> str:
    path = (file or "").replace("\\", "/")
    if path.startswith("./"):
        path = path[2:]
    return path


def _is_ci_pipeline(path: str) -> bool:
    """True for a CI pipeline definition in any common host, not a test module."""
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    if name in _CI_PIPELINE_NAMES or name.startswith("jenkinsfile"):
        return True
    markers = (
        ".github/workflows/",
        ".circleci/",
        ".buildkite/",
    )
    return any(
        lowered.startswith(marker) or f"/{marker}" in f"/{lowered}"
        for marker in markers
    )


def _is_gitignore_secret_claim(path: str, category: str) -> bool:
    """Fast Brain measures secret patterns in any repository's .gitignore."""
    return (
        path.rsplit("/", 1)[-1] == ".gitignore"
        and category in _GITIGNORE_SECRET_CATEGORIES
    )


def is_unmeasured_model_claim(issue: Issue) -> bool:
    """True when the model is restating a measurement or a CI pipeline file.

    Complexity and ``heuristic.*`` / ``pack.*`` come from Fast Brain. A CI
    pipeline file is not a unit-test module. Secret patterns in ``.gitignore``
    are measured by Fast Brain for every repository.
    """
    cat = (issue.category or "").strip().lower()
    path = _normalise_repo_path(issue.file)
    if cat == "quality.complexity":
        return True
    if cat.startswith("heuristic.") or cat.startswith("pack."):
        return True
    if cat in _TESTING_CATEGORIES and _is_ci_pipeline(path):
        return True
    return _is_gitignore_secret_claim(path, cat)


def merge_reports(
    parts: list[FindingReport],
    heuristic_issues: list[Issue],
) -> FindingReport:
    """Merge LLM pass reports + heuristics; dedupe by (file, title).

    Confidence is the minimum across non-empty parts (parts with no issues and
    no durabilityGaps are ignored). When no such parts remain, confidence is 0.
    """
    issue_stream: list[Issue] = list(heuristic_issues)
    for part in parts:
        issue_stream.extend(
            issue.model_copy(update={"source": "llm"})
            for issue in part.issues
            if not is_unmeasured_model_claim(issue)
        )

    scores = next((p.scores for p in parts if p.scores is not None), None)
    scanner_runs = [run for part in parts for run in part.scannerRuns]

    report = FindingReport(
        confidence=_min_confidence(parts),
        summary=Summary(),
        issues=_dedupe_issues(issue_stream),
        durabilityGaps=_combine_gaps(parts),
        scores=scores,
        scannerRuns=scanner_runs,
    )
    report.summary = report.recount_summary()
    return report
