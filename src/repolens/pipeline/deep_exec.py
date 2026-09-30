"""Deep multi-pass analysis and coverage metric application."""

from __future__ import annotations

from pathlib import Path

from repolens.adaptive import sync_project_fingerprints
from repolens.bands import coerce_issue_bands
from repolens.config import RepoLensConfig
from repolens.coverage import (
    CoverageResult,
    evaluate_coverage,
    explain_missed_id,
    is_lazy_na_reason,
    parse_coverage_notes,
    reopen_hollow_bands,
)
from repolens.deep import (
    merge_reports,
    plan_deep_passes,
)
from repolens.heuristics import HeuristicResult, run_heuristics
from repolens.inventory import FileEntry
from repolens.llm import default_model, resolve_llm_timeout
from repolens.llm.model_lock import bind_lock_context, reset_lock_context
from repolens.metrics import compute_audit_metrics, low_audit_explanations
from repolens.pipeline.deep_pass import _apply_coverage_closure
from repolens.pipeline.deep_pass import (
    _ollama_wait_bits as _ollama_wait_bits,
)
from repolens.pipeline.deep_pass import (
    _pass_report as _pass_report,
)
from repolens.pipeline.pass_cache import pass_label
from repolens.pipeline.pass_resume import (
    note_timed_out_passes,
    raise_aborted,
    run_or_resume_pass,
    snapshot_finished,
)
from repolens.progress import ReviewProgress
from repolens.rules.registry import Rule, load_enabled_rules
from repolens.schema import CoverageBlock, FindingReport, ScannerRun
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


def _sync_adaptive_cache(
    root: Path,
    files: list[FileEntry],
    *,
    cfg: RepoLensConfig,
    prog: ReviewProgress,
):
    """Open store, sync fingerprints, return (store, diff) or (None, None)."""
    if not cfg.adaptive.enabled:
        return None, None
    from repolens.learning.store import ProjectStore

    try:
        from repolens.inventory import classify_fingerprint_deletions

        store = ProjectStore(root)
        store.open()
        diff = sync_project_fingerprints(store, files)
        removed, dropped = classify_fingerprint_deletions(root, list(diff.deleted))
        bits = [
            f"+{len(diff.added)} added",
            f"~{len(diff.changed)} changed",
        ]
        if removed:
            bits.append(f"-{len(removed)} removed from tree")
        if dropped:
            bits.append(f"{len(dropped)} dropped from inventory pack")
        if not removed and not dropped:
            bits.append("-0 removed from tree")
        prog.phase("Cache: " + ", ".join(bits))
        if prog.verbose and (diff.added or diff.changed or removed or dropped):
            if diff.added:
                prog.detail("added: " + ", ".join(diff.added[:8]))
            if diff.changed:
                prog.detail("changed: " + ", ".join(diff.changed[:8]))
            if removed:
                prog.detail("removed from tree: " + ", ".join(removed[:8]))
            if dropped:
                prog.detail(
                    "dropped from inventory pack (still on disk; over max_files): "
                    + ", ".join(dropped[:8])
                )
        return store, diff
    except OSError as exc:
        prog.phase(f"Cache: skipped ({exc})")
        return None, None


def _maybe_sync_fts(store, root: Path, files: list[FileEntry], diff) -> None:
    from repolens.learning.consent import has_consent

    if store is None or diff is None or not has_consent(root):
        return
    for path in diff.deleted:
        store.delete_chunk(path)
    touch = set(diff.added) | set(diff.changed)
    for entry in files:
        if entry.relative not in touch:
            continue
        try:
            text = entry.path.read_text(encoding="utf-8", errors="replace")[:80_000]
        except OSError:
            continue
        store.upsert_chunk(entry.relative, text)


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


def _apply_coverage_metrics(
    report: FindingReport,
    coverage: CoverageResult,
    *,
    pass_confidences: dict[str, int],
    scanner_runs: list[ScannerRun] | None = None,
) -> FindingReport:
    """Set gate + band audit confidences; rewrite lazy N/A gaps to missed."""
    runs: list[ScannerRun] = list(scanner_runs or report.scannerRuns)
    metrics = compute_audit_metrics(
        pass_confidences=pass_confidences,
        coverage=coverage,
        scanner_runs=runs,
        issues=report.issues,
    )
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


def _load_deep_heuristics(
    *,
    root: Path,
    files: list[FileEntry],
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    heur_result: HeuristicResult | None,
    pack_ids: list,
) -> HeuristicResult:
    if heur_result is not None:
        prog.phase("→ Deep: using Fast Brain heuristics…")
        heur = heur_result
    else:
        prog.phase("→ Deep: heuristics…")
        heur = run_heuristics(
            root,
            files,
            mega_file_lines=cfg.deep.mega_file_lines,
            mega_file_exclude_globs=cfg.deep.extra_skip_globs() or None,
            pack_ids=pack_ids or None,
            workers=cfg.fast_brain.parallel_workers,
            near_clones_config=cfg.fast_brain.near_clones,
        )
    if prog.verbose:
        prog.detail(
            f"heuristics: {len(heur.issues)} issue(s), "
            f"{len(heur.hot_paths)} hot path(s)"
        )
    return heur


def _announce_deep_runtime(
    prog: ReviewProgress, passes: list, cfg: RepoLensConfig
) -> None:
    if prog.quiet or not passes:
        return
    from repolens.runtime_estimate import estimate_deep_runtime

    est = estimate_deep_runtime(
        files=len(passes[0].files) if passes else 0,
        passes=len(passes),
        provider=cfg.model.provider or "unknown",
    )
    prog.phase(est)




def _ordered_unique(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for cid in ids:
        if cid in seen:
            continue
        seen.add(cid)
        unique.append(cid)
    return unique


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




def _analyze_deep_passes(
    *,
    root: Path,
    mode: str,
    full_audit: bool,
    files: list[FileEntry],
    llm_files: list[FileEntry],
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    prompt_prefix: str = "",
    scanner_runs: list | None = None,
    scanner_issues: list | None = None,
    heur_result: HeuristicResult | None = None,
    out_dir: Path | None = None,
    fmt: str = "md",
    report_when: object | None = None,
) -> FindingReport:
    """Heuristics → plan passes → structured LLM per pass → merge + coverage."""
    pack_ids = list(cfg.packs.enabled)
    heur = _load_deep_heuristics(
        root=root,
        files=files,
        cfg=cfg,
        prog=prog,
        heur_result=heur_result,
        pack_ids=pack_ids,
    )
    rules: list[Rule] = load_enabled_rules(project_root=root)
    passes = plan_deep_passes(
        mode,
        full_audit=full_audit,
        entries=llm_files or files,
        hot_paths=heur.hot_paths,
        adaptive_paths=[e.relative for e in llm_files],
        chars_per_pass=cfg.deep.chars_per_pass,
        rules=rules,
        max_passes=cfg.deep.max_passes,
    )
    _announce_deep_runtime(prog, passes, cfg)

    parts: list[FindingReport] = []
    raw_by_pass: dict[str, str] = {}
    degraded_by_pass: dict[str, bool] = {}
    repair_attempts_total = 0
    all_coverage_ids: list[str] = []
    raw_dir = root / ".repolens"
    n = len(passes)
    provider = cfg.model.provider or "unknown"
    model_name = cfg.model.model or default_model(cfg.model.provider)
    timeout = resolve_llm_timeout(cfg.model)
    finished_labels: list[str] = []
    timed_out_labels: list[str] = []
    try:
        for idx, deep_pass in enumerate(passes, start=1):
            part, raw, degraded, attempts = run_or_resume_pass(
                root=root,
                idx=idx,
                n=n,
                deep_pass=deep_pass,
                rules=rules,
                pack_ids=pack_ids,
                prompt_prefix=prompt_prefix,
                cfg=cfg,
                prog=prog,
                raw_dir=raw_dir,
                model_name=model_name,
                provider=provider,
                timeout=timeout,
            )
            parts.append(part)
            raw_by_pass[deep_pass.name] = raw
            degraded_by_pass[deep_pass.name] = degraded
            repair_attempts_total += attempts
            all_coverage_ids.extend(deep_pass.coverage_ids)
            label = pass_label(deep_pass.name)
            if degraded and any(
                "timed out" in gap.lower() for gap in part.durabilityGaps
            ):
                timed_out_labels.append(label)
            elif not degraded:
                finished_labels.append(label)
                snapshot_finished(
                    merge_reports(parts, heur.issues),
                    out_dir,
                    fmt,
                    finished_labels,
                    mode,
                    report_when,
                )
    except KeyboardInterrupt:
        raise_aborted(parts, heur.issues, finished_labels)

    report = note_timed_out_passes(
        merge_reports(parts, heur.issues),
        timed_out_labels,
        finished_labels,
    )
    if repair_attempts_total:
        report.llmRepairAttempts = repair_attempts_total
        prog.detail(f"LLM JSON micro-repair attempts: {repair_attempts_total}")
    report = _fold_scanners(report, scanner_issues, cfg, prog)
    unique_ids = _ordered_unique(all_coverage_ids)
    coverage = evaluate_coverage(
        unique_ids,
        report.issues,
        report.durabilityGaps,
        seeded_na=cfg.coverage.na,
        seeded_covered=cfg.coverage.covered,
    )
    if coverage.missed:
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
            raise_aborted(parts, heur.issues, finished_labels)
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
        coverage = evaluate_coverage(
            unique_ids,
            report.issues,
            report.durabilityGaps,
            seeded_na=cfg.coverage.na,
            seeded_covered=cfg.coverage.covered,
        )
    report, pass_confidences = build_pass_confidences_with_floors(
        _pass_outcomes(passes, parts, raw_by_pass, degraded_by_pass),
        coverage=coverage,
        scanner_runs=scanner_runs,
        config_floor=cfg.deep.vacuous_pass_confidence_floor,
        report=report,
    )
    coverage = reopen_hollow_bands(coverage, report.durabilityGaps)
    report = _apply_coverage_metrics(
        report,
        coverage,
        pass_confidences=pass_confidences,
        scanner_runs=scanner_runs,
    )
    report.coverage = CoverageBlock(
        covered=list(coverage.covered),
        na=dict(coverage.na),
        missed=list(coverage.missed),
        missedNotes={
            cid: explain_missed_id(cid, report.durabilityGaps) for cid in coverage.missed
        },
    )
    from repolens.themes import build_theme_breakdown

    report.themes = build_theme_breakdown(
        coverage,
        report.issues,
        mode=mode,
        full_audit=full_audit,
    )
    report.scoreNotes = low_audit_explanations(report)
    _phase_coverage_metrics(prog, report, coverage, unique_ids)
    return report
