from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from repolens.coverage import CoverageResult
from repolens.schema import FindingReport, ScannerRun

RAW_ANALYSIS_EVIDENCE_MIN = 100
SkipReason = Literal[
    "pass_degraded", "no_analysis_evidence", "checklist_incomplete"
]


def is_floor_candidate(report: FindingReport) -> bool:
    return report.confidence == 0 and len(report.issues) == 0


def has_analysis_evidence(
    report: FindingReport, raw_response_text: str = ""
) -> bool:
    for field in ("analysisNotes", "narrative", "notes"):
        val = getattr(report, field, None)
        if isinstance(val, str) and len(val.strip()) >= 20:
            return True
    return len(raw_response_text.strip()) >= RAW_ANALYSIS_EVIDENCE_MIN


def resolve_floor_value(
    *, scanners_all_ran: bool, config_floor: int | None
) -> int | None:
    if config_floor == 0:
        return None
    if config_floor is not None:
        return max(1, min(100, int(config_floor)))
    return 75 if scanners_all_ran else 55


def skip_reason(
    *,
    degraded: bool,
    has_evidence: bool,
    checklist_complete: bool,
) -> SkipReason | None:
    if degraded:
        return "pass_degraded"
    if not has_evidence:
        return "no_analysis_evidence"
    if not checklist_complete:
        return "checklist_incomplete"
    return None


def is_finding_like_gap(gap: str) -> bool:
    g = gap.strip()
    if g.startswith("Two-Lane:"):
        return False
    if g.startswith("metrics.vacuous_pass_"):
        return False
    if g.startswith("coverage:") and "missed" in g:
        return True
    if g.startswith("llm.schema_invalid:"):
        return True
    return False


def is_vacuous_for_floor(report: FindingReport, *, degraded: bool) -> bool:
    if degraded:
        return False
    if report.confidence != 0 or report.issues:
        return False
    return not any(is_finding_like_gap(g) for g in report.durabilityGaps)


def checklist_complete_for_scored(
    coverage: CoverageResult, scored_prefixes: Iterable[str]
) -> bool:
    prefixes = tuple(scored_prefixes)
    if not prefixes:
        return True

    def in_scope(cid: str) -> bool:
        return any(cid.startswith(p) for p in prefixes)

    if any(in_scope(m) for m in coverage.missed):
        return False
    if any(in_scope(i) for i in coverage.invalid_na):
        return False
    return True


def scanners_all_ran(runs: list[ScannerRun]) -> bool:
    return bool(runs) and all(r.status == "ran" for r in runs)


@dataclass(frozen=True)
class PassFloorInput:
    name: str
    report: FindingReport
    raw_text: str
    degraded: bool


@dataclass(frozen=True)
class PassFloorResult:
    pass_confidences: dict[str, int]
    notes: list[str]


def apply_vacuous_pass_floors(
    passes: list[PassFloorInput],
    *,
    coverage: CoverageResult,
    scanner_runs: list[ScannerRun],
    config_floor: int | None,
    scored_prefixes: tuple[str, ...] = ("sec.", "rel.", "arch."),
) -> PassFloorResult:
    """Substitute pass bases for eligible vacuous candidates; emit notes."""
    ran = scanners_all_ran(scanner_runs)
    floor = resolve_floor_value(scanners_all_ran=ran, config_floor=config_floor)
    complete = checklist_complete_for_scored(coverage, scored_prefixes)
    confidences: dict[str, int] = {}
    notes: list[str] = []

    for item in passes:
        report = item.report
        confidences[item.name] = report.confidence
        if not is_floor_candidate(report):
            continue
        if floor is None:
            continue
        evidence = has_analysis_evidence(report, item.raw_text)
        reason = skip_reason(
            degraded=item.degraded,
            has_evidence=evidence,
            checklist_complete=complete,
        )
        if reason is None and is_vacuous_for_floor(report, degraded=item.degraded):
            confidences[item.name] = floor
            notes.append(
                "metrics.vacuous_pass_confidence_floored:"
                f"{item.name}={floor} (scanners_ran={str(ran).lower()}, "
                "checklist=complete)"
            )
        else:
            code = reason or "no_analysis_evidence"
            notes.append(
                f"metrics.vacuous_pass_floor_skipped:{item.name}={code}"
            )
    return PassFloorResult(pass_confidences=confidences, notes=notes)
