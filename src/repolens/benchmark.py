"""Supporting benchmark metrics from FindingReport (Phase 6.6).

Headline human metrics (remediation rate, MTTR, suggested-fix apply %) are
defined in ``docs/benchmarks/methodology.md`` and require a study protocol.
This module scores **supporting** actionability signals from an existing report
so dogfood and CI can publish honest precursor numbers without inventing F1.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from repolens.schema import FindingReport, Issue, Severity


@dataclass(frozen=True)
class ActionabilityScores:
    """Proxy metrics derived from a single FindingReport."""

    total_issues: int
    critical_high: int
    critical_high_with_code_example: int
    medium_low: int
    medium_low_with_code_example: int
    issues_with_code_example: int
    # Fraction of all issues with non-empty codeExample; None if empty report.
    suggested_fix_readiness: float | None
    issues_with_impact: int
    scanner_sourced: int
    llm_sourced: int
    heuristic_sourced: int
    location_verified: int
    location_unverified: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _ActionabilityTally:
    critical_high: int = 0
    critical_high_with_code_example: int = 0
    medium_low: int = 0
    medium_low_with_code_example: int = 0
    issues_with_code_example: int = 0
    issues_with_impact: int = 0
    scanner_sourced: int = 0
    llm_sourced: int = 0
    heuristic_sourced: int = 0
    location_verified: int = 0
    location_unverified: int = 0


def _has_code_example(issue: Issue) -> bool:
    return bool((issue.codeExample or "").strip())


def _count_severity_examples(
    issue: Issue, has_example: bool, tally: _ActionabilityTally
) -> None:
    if issue.severity in {Severity.CRITICAL, Severity.HIGH}:
        tally.critical_high += 1
        if has_example:
            tally.critical_high_with_code_example += 1
        return
    tally.medium_low += 1
    if has_example:
        tally.medium_low_with_code_example += 1


def _count_source(issue: Issue, tally: _ActionabilityTally) -> None:
    if issue.source == "scanner":
        tally.scanner_sourced += 1
    elif issue.source == "heuristic":
        tally.heuristic_sourced += 1
    elif issue.source == "llm":
        tally.llm_sourced += 1


def _count_location(issue: Issue, tally: _ActionabilityTally) -> None:
    if issue.locationVerified is True:
        tally.location_verified += 1
    elif issue.locationVerified is False:
        tally.location_unverified += 1


def _tally_issue(issue: Issue, tally: _ActionabilityTally) -> None:
    has_example = _has_code_example(issue)
    if has_example:
        tally.issues_with_code_example += 1
    if (issue.impact or "").strip():
        tally.issues_with_impact += 1
    _count_severity_examples(issue, has_example, tally)
    _count_source(issue, tally)
    _count_location(issue, tally)


def score_actionability(report: FindingReport) -> ActionabilityScores:
    """Compute supporting actionability metrics for one report."""
    tally = _ActionabilityTally()
    for issue in report.issues:
        _tally_issue(issue, tally)
    total = len(report.issues)
    readiness = (tally.issues_with_code_example / total) if total else None
    return ActionabilityScores(
        total_issues=total,
        critical_high=tally.critical_high,
        critical_high_with_code_example=tally.critical_high_with_code_example,
        medium_low=tally.medium_low,
        medium_low_with_code_example=tally.medium_low_with_code_example,
        issues_with_code_example=tally.issues_with_code_example,
        suggested_fix_readiness=readiness,
        issues_with_impact=tally.issues_with_impact,
        scanner_sourced=tally.scanner_sourced,
        llm_sourced=tally.llm_sourced,
        heuristic_sourced=tally.heuristic_sourced,
        location_verified=tally.location_verified,
        location_unverified=tally.location_unverified,
    )


def score_actionability_file(path: Path) -> ActionabilityScores:
    """Load FindingReport JSON and score it."""
    data = json.loads(path.read_text(encoding="utf-8"))
    report = FindingReport.model_validate(data)
    return score_actionability(report)
