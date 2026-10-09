"""Merge planned pass results and finish deep analysis."""

from __future__ import annotations

from pathlib import Path

from repolens.bands import coerce_issue_bands
from repolens.config import RepoLensConfig
from repolens.coverage import CoverageResult
from repolens.inventory import FileEntry
from repolens.pipeline.deep_exec_coverage import (
    _ordered_unique,
    _run_coverage_closure_if_needed,
    _stamp_coverage_and_themes,
)
from repolens.progress import ReviewProgress
from repolens.schema import FindingReport, ScannerRun
from repolens.vacuous_floor import PassFloorInput, apply_vacuous_pass_floors


def build_pass_confidences_with_floors(
    outcomes: list[PassFloorInput],
    *,
    coverage: CoverageResult,
    scanner_runs: list[ScannerRun] | None,
    config_floor: int | None,
    report: FindingReport,
) -> tuple[FindingReport, dict[str, int]]:
    """Apply vacuous floors, append notes to *report*, return floored bases."""
    floor_result = apply_vacuous_pass_floors(
        outcomes,
        coverage=coverage,
        scanner_runs=list(scanner_runs or []),
        config_floor=config_floor,
    )
    for note in floor_result.notes:
        if note not in report.durabilityGaps:
            report.durabilityGaps.append(note)
    return report, floor_result.pass_confidences


def is_vacuous_llm_report(report: FindingReport) -> bool:
    """True when the model returned a schema-valid but empty/useless report.

    For vacuous *pass confidence flooring* (gap filtering, degraded skips),
    prefer :func:`repolens.vacuous_floor.is_vacuous_for_floor` /
    :func:`repolens.vacuous_floor.is_finding_like_gap`.
    """
    return (
        report.confidence == 0
        and not report.issues
        and not report.durabilityGaps
    )


def _fold_scanners(
    report: FindingReport,
    scanner_issues: list | None,
    cfg: RepoLensConfig,
    prog: ReviewProgress,
) -> FindingReport:
    from repolens.fp_calibrations import apply_fp_calibrations
    from repolens.scanners.sca import apply_cross_source_sca_dedupe

    report.issues = coerce_issue_bands(report.issues)
    report.issues = apply_fp_calibrations(report.issues, cfg.deep)
    if scanner_issues:
        report.issues = list(report.issues) + list(scanner_issues)
    before_cross = len(report.issues)
    report = apply_cross_source_sca_dedupe(report)
    if len(report.issues) < before_cross:
        prog.detail(
            f"SCA: collapsed {before_cross - len(report.issues)} "
            "cross-source advisory duplicate(s)"
        )
    report.summary = report.recount_summary()
    return report


def _pass_outcomes(
    passes,
    parts: list[FindingReport],
    raw_by_pass: dict[str, str],
    degraded_by_pass: dict[str, bool],
) -> list[PassFloorInput]:
    return [
        PassFloorInput(
            name=deep_pass.name,
            report=part,
            raw_text=raw_by_pass.get(deep_pass.name, ""),
            degraded=degraded_by_pass.get(deep_pass.name, False),
        )
        for deep_pass, part in zip(passes, parts, strict=False)
    ]


def _merge_planned_pass_results(
    *,
    parts: list[FindingReport],
    heur_issues: list,
    timed_out_labels: list[str],
    finished_labels: list[str],
    p3_gaps: list[str],
    repair_attempts_total: int,
    scanner_issues: list | None,
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    llm_files: list[FileEntry],
    files: list[FileEntry],
    root: Path,
) -> FindingReport:
    from repolens.deep import merge_reports
    from repolens.na_truth import reject_false_na_claims
    from repolens.pipeline.pass_resume import note_timed_out_passes

    report = note_timed_out_passes(
        merge_reports(parts, heur_issues),
        timed_out_labels,
        finished_labels,
    )
    if p3_gaps:
        report.durabilityGaps = list(report.durabilityGaps) + list(p3_gaps)
    if repair_attempts_total:
        report.llmRepairAttempts = repair_attempts_total
        prog.detail(f"LLM JSON micro-repair attempts: {repair_attempts_total}")
    report = _fold_scanners(report, scanner_issues, cfg, prog)
    report.durabilityGaps = reject_false_na_claims(
        list(report.durabilityGaps),
        llm_files or files,
        root=root,
    )
    return report


def _finish_deep_after_passes(
    *,
    root: Path,
    mode: str,
    full_audit: bool,
    files: list[FileEntry],
    llm_files: list[FileEntry],
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    scanner_runs: list | None,
    scanner_issues: list | None,
    passes: list,
    parts: list[FindingReport],
    raw_by_pass: dict[str, str],
    degraded_by_pass: dict[str, bool],
    repair_attempts_total: int,
    all_coverage_ids: list[str],
    finished_labels: list[str],
    timed_out_labels: list[str],
    heur_issues: list,
    p3_gaps: list[str],
    raw_dir: Path,
    out_dir: Path | None,
    fmt: str,
    report_when: object | None,
) -> FindingReport:
    from repolens.coverage import evaluate_coverage

    report = _merge_planned_pass_results(
        parts=parts, heur_issues=heur_issues, timed_out_labels=timed_out_labels,
        finished_labels=finished_labels, p3_gaps=p3_gaps,
        repair_attempts_total=repair_attempts_total, scanner_issues=scanner_issues,
        cfg=cfg, prog=prog, llm_files=llm_files, files=files, root=root,
    )
    unique_ids = _ordered_unique(all_coverage_ids)
    coverage = evaluate_coverage(
        unique_ids, report.issues, report.durabilityGaps,
        seeded_na=cfg.coverage.na, seeded_covered=cfg.coverage.covered,
    )
    report, coverage = _run_coverage_closure_if_needed(
        report=report, coverage=coverage, unique_ids=unique_ids, cfg=cfg, prog=prog,
        raw_dir=raw_dir, root=root, parts=parts, heur_issues=heur_issues,
        finished_labels=finished_labels, out_dir=out_dir, fmt=fmt, mode=mode,
        report_when=report_when,
    )
    report, pass_confidences = build_pass_confidences_with_floors(
        _pass_outcomes(passes, parts, raw_by_pass, degraded_by_pass),
        coverage=coverage, scanner_runs=scanner_runs,
        config_floor=cfg.deep.vacuous_pass_confidence_floor, report=report,
    )
    degraded = frozenset(
        name for name, flag in degraded_by_pass.items() if flag
    )
    return _stamp_coverage_and_themes(
        report=report, coverage=coverage, pass_confidences=pass_confidences,
        scanner_runs=scanner_runs, mode=mode, full_audit=full_audit,
        prog=prog, unique_ids=unique_ids, degraded_passes=degraded,
    )
