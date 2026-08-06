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

from repolens.schema import FindingReport, Severity


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


def score_actionability(report: FindingReport) -> ActionabilityScores:
    """Compute supporting actionability metrics for one report."""
    total = len(report.issues)
    crit_high = 0
    crit_high_ex = 0
    medium_low = 0
    medium_low_ex = 0
    with_ex = 0
    with_impact = 0
    scanner = 0
    llm = 0
    heur = 0
    verified = 0
    unverified = 0

    for issue in report.issues:
        has_ex = bool((issue.codeExample or "").strip())
        if has_ex:
            with_ex += 1
        if (issue.impact or "").strip():
            with_impact += 1
        if issue.severity in {Severity.CRITICAL, Severity.HIGH}:
            crit_high += 1
            if has_ex:
                crit_high_ex += 1
        else:
            medium_low += 1
            if has_ex:
                medium_low_ex += 1
        src = issue.source
        if src == "scanner":
            scanner += 1
        elif src == "heuristic":
            heur += 1
        elif src == "llm":
            llm += 1
        if issue.locationVerified is True:
            verified += 1
        elif issue.locationVerified is False:
            unverified += 1

    readiness = (with_ex / total) if total else None
    return ActionabilityScores(
        total_issues=total,
        critical_high=crit_high,
        critical_high_with_code_example=crit_high_ex,
        medium_low=medium_low,
        medium_low_with_code_example=medium_low_ex,
        issues_with_code_example=with_ex,
        suggested_fix_readiness=readiness,
        issues_with_impact=with_impact,
        scanner_sourced=scanner,
        llm_sourced=llm,
        heuristic_sourced=heur,
        location_verified=verified,
        location_unverified=unverified,
    )


def score_actionability_file(path: Path) -> ActionabilityScores:
    """Load FindingReport JSON and score it."""
    data = json.loads(path.read_text(encoding="utf-8"))
    report = FindingReport.model_validate(data)
    return score_actionability(report)
