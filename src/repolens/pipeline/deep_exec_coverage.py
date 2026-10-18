"""Coverage metrics, closure, and theme stamping for deep analysis."""

from __future__ import annotations

from repolens.config import RepoLensConfig
from repolens.coverage import (
    CoverageResult,
    is_lazy_na_reason,
    parse_coverage_notes,
)
from repolens.metrics import compute_audit_metrics
from repolens.pipeline.deep_job import DeepJob
from repolens.progress import ReviewProgress
from repolens.schema import FindingReport, ScannerRun


def _seeded_coverage(
    cfg: RepoLensConfig,
    *,
    full_audit: bool,
    change_set: object | None,
) -> tuple[dict[str, str], dict[str, str]]:
    from repolens.blast_radius import merge_blast_radius_coverage_seeds

    return merge_blast_radius_coverage_seeds(
        cfg.coverage.na,
        cfg.coverage.covered,
        full_audit=full_audit,
        change_set=change_set,
    )


def _ordered_unique(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for cid in ids:
        if cid in seen:
            continue
        seen.add(cid)
        unique.append(cid)
    return unique


def _apply_coverage_metrics(
    report: FindingReport,
    coverage: CoverageResult,
    *,
    pass_confidences: dict[str, int],
    scanner_runs: list[ScannerRun] | None = None,
    degraded_passes: set[str] | frozenset[str] | None = None,
) -> FindingReport:
    """Set gate + band audit confidences; rewrite lazy N/A gaps to missed.

    ``degraded_passes`` must come from pipeline execution state
    (``degraded_by_pass``), never from model-authored ``durabilityGaps``.
    """
    runs: list[ScannerRun] = list(scanner_runs or report.scannerRuns)
    metrics = compute_audit_metrics(
        pass_confidences=pass_confidences,
        coverage=coverage,
        scanner_runs=runs,
        issues=report.issues,
        degraded_passes=degraded_passes or (),
    )
    report.auditIncomplete = metrics.audit_incomplete
    report.confidence = metrics.gate_confidence
    report.securityAuditConfidence = metrics.security_audit_confidence
    report.architectureAuditConfidence = metrics.architecture_audit_confidence
    report.reliabilityAuditConfidence = metrics.reliability_audit_confidence
    report.summary = report.recount_summary()

    cleaned: list[str] = []
    for gap in report.durabilityGaps:
        notes = parse_coverage_notes([gap])
        if notes:
            cid, reason = next(iter(notes.items()))
            if is_lazy_na_reason(reason):
                missed_gap = f"coverage:{cid}: missed — lazy N/A rejected ({reason})"
                if missed_gap not in cleaned:
                    cleaned.append(missed_gap)
                continue
        cleaned.append(gap)
    for mid in coverage.missed:
        marker = f"coverage:{mid}: missed"
        if not any(marker in g for g in cleaned):
            cleaned.append(f"coverage:{mid}: missed — neither issue nor N/A")
    report.durabilityGaps = cleaned
    return report


def _phase_coverage_metrics(
    prog: ReviewProgress,
    report: FindingReport,
    coverage: CoverageResult,
    unique_ids: list[str],
) -> None:
    if not unique_ids:
        return
    prog.phase(
        f"Coverage: {len(coverage.covered)} covered · "
        f"{len(coverage.na)} N/A · {len(coverage.missed)} missed"
    )
    metric_bits = [f"gate {report.confidence}%"]
    if report.securityAuditConfidence is not None:
        metric_bits.append(f"security audit {report.securityAuditConfidence}%")
    if report.reliabilityAuditConfidence is not None:
        metric_bits.append(f"reliability audit {report.reliabilityAuditConfidence}%")
    if report.architectureAuditConfidence is not None:
        metric_bits.append(f"architecture audit {report.architectureAuditConfidence}%")
    prog.phase("Metrics: " + " · ".join(metric_bits))


def _run_coverage_closure_if_needed(job: DeepJob) -> tuple[FindingReport, CoverageResult]:
    report = job.report
    coverage = job.coverage
    unique_ids = job.unique_ids
    cfg = job.cfg
    prog = job.prog
    raw_dir = job.raw_dir
    root = job.root
    parts = job.parts
    heur_issues = job.heur_issues
    finished_labels = job.finished_labels
    out_dir = job.out_dir
    fmt = job.fmt
    mode = job.mode
    report_when = job.report_when
    full_audit = job.full_audit
    change_set = job.change_set
    from repolens.coverage import evaluate_coverage
    from repolens.llm.model_lock import bind_lock_context, reset_lock_context
    from repolens.pipeline.deep_pass import _apply_coverage_closure
    from repolens.pipeline.pass_resume import raise_aborted, snapshot_finished

    if not coverage.missed:
        return report, coverage
    token = bind_lock_context(
        repo=root.name,
        path=str(root),
        pass_name="Coverage closure",
        status=prog.phase,
    )
    gap_before = len(report.durabilityGaps)
    try:
        report = _apply_coverage_closure(
            report,
            list(coverage.missed),
            cfg=cfg,
            prog=prog,
            raw_dir=raw_dir,
        )
    except KeyboardInterrupt:
        raise_aborted(parts, heur_issues, finished_labels, root=root)
    finally:
        reset_lock_context(token)
    fresh = report.durabilityGaps[gap_before:]
    if not any("timed out" in gap.lower() for gap in fresh):
        snapshot_finished(
            report,
            out_dir,
            fmt,
            finished_labels + ["Coverage closure"],
            mode,
            report_when,
        )
    seeded_na, seeded_covered = _seeded_coverage(
        cfg, full_audit=full_audit, change_set=change_set
    )
    coverage = evaluate_coverage(
        unique_ids,
        report.issues,
        report.durabilityGaps,
        seeded_na=seeded_na,
        seeded_covered=seeded_covered,
    )
    return report, coverage


def _stamp_coverage_and_themes(job: DeepJob) -> FindingReport:
    report = job.report
    coverage = job.coverage
    pass_confidences = job.pass_confidences
    scanner_runs = job.scanner_runs
    mode = job.mode
    full_audit = job.full_audit
    prog = job.prog
    unique_ids = job.unique_ids
    degraded_passes = job.degraded_passes
    from repolens.coverage import explain_missed_id, reopen_hollow_bands
    from repolens.metrics import low_audit_explanations
    from repolens.schema import CoverageBlock
    from repolens.themes import build_theme_breakdown

    coverage = reopen_hollow_bands(coverage, report.durabilityGaps)
    report = _apply_coverage_metrics(
        report,
        coverage,
        pass_confidences=pass_confidences,
        scanner_runs=scanner_runs,
        degraded_passes=degraded_passes,
    )
    report.coverage = CoverageBlock(
        covered=list(coverage.covered),
        na=dict(coverage.na),
        missed=list(coverage.missed),
        missedNotes={
            cid: explain_missed_id(cid, report.durabilityGaps) for cid in coverage.missed
        },
    )
    report.themes = build_theme_breakdown(
        coverage,
        report.issues,
        mode=mode,
        full_audit=full_audit,
    )
    report.scoreNotes = low_audit_explanations(report)
    _phase_coverage_metrics(prog, report, coverage, unique_ids)
    return report
