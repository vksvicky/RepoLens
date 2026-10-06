"""Deep multi-pass analysis and coverage metric application."""

from __future__ import annotations

from pathlib import Path

from repolens.config import RepoLensConfig
from repolens.coverage import (
    evaluate_coverage,
    explain_missed_id,
    reopen_hollow_bands,
)
from repolens.deep import (
    merge_reports,
    plan_deep_passes,
)
from repolens.heuristics import HeuristicResult
from repolens.inventory import FileEntry
from repolens.llm import default_model, resolve_llm_timeout
from repolens.llm.model_lock import bind_lock_context, reset_lock_context
from repolens.metrics import low_audit_explanations
from repolens.pipeline.deep_exec_support import (  # noqa: F401 — re-export for callers
    _announce_deep_runtime,
    _apply_coverage_metrics,
    _fold_scanners,
    _load_deep_heuristics,
    _maybe_sync_fts,
    _ordered_unique,
    _pass_outcomes,
    _phase_coverage_metrics,
    _sync_adaptive_cache,
    build_pass_confidences_with_floors,
    is_vacuous_llm_report,
)
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
from repolens.schema import CoverageBlock, FindingReport


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
    skip_cache: bool = False,
    graph: object | None = None,
) -> FindingReport:
    """Heuristics → plan passes → structured LLM per pass → merge + coverage."""
    from datetime import UTC, datetime

    from repolens.pipeline.journal import append_event

    append_event(
        root,
        "review_started",
        run_id=datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ"),
        model=cfg.model.model or default_model(cfg.model.provider),
        role_packs=bool(cfg.deep.role_packs),
        provider=cfg.model.provider,
    )
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
    p3_gaps: list[str] = []
    passes = plan_deep_passes(
        mode,
        full_audit=full_audit,
        entries=llm_files or files,
        hot_paths=heur.hot_paths,
        adaptive_paths=[e.relative for e in llm_files],
        chars_per_pass=cfg.deep.chars_per_pass,
        rules=rules,
        max_passes=cfg.deep.max_passes,
        role_packs=bool(cfg.deep.role_packs),
        graph=graph,  # type: ignore[arg-type]
        durability_gaps_out=p3_gaps,
    )
    _announce_deep_runtime(prog, passes, cfg)
    raw_dir = root / ".repolens"
    (
        parts,
        raw_by_pass,
        degraded_by_pass,
        repair_attempts_total,
        all_coverage_ids,
        finished_labels,
        timed_out_labels,
    ) = _run_planned_passes(
        root=root,
        passes=passes,
        rules=rules,
        pack_ids=pack_ids,
        prompt_prefix=prompt_prefix,
        cfg=cfg,
        prog=prog,
        raw_dir=raw_dir,
        skip_cache=skip_cache,
        heur_issues=heur.issues,
        out_dir=out_dir,
        fmt=fmt,
        mode=mode,
        report_when=report_when,
    )

    report = note_timed_out_passes(
        merge_reports(parts, heur.issues),
        timed_out_labels,
        finished_labels,
    )
    if p3_gaps:
        report.durabilityGaps = list(report.durabilityGaps) + list(p3_gaps)
    if repair_attempts_total:
        report.llmRepairAttempts = repair_attempts_total
        prog.detail(f"LLM JSON micro-repair attempts: {repair_attempts_total}")
    report = _fold_scanners(report, scanner_issues, cfg, prog)
    from repolens.na_truth import reject_false_na_claims

    report.durabilityGaps = reject_false_na_claims(
        list(report.durabilityGaps),
        llm_files or files,
        root=root,
    )
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
            raise_aborted(parts, heur.issues, finished_labels, root=root)
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


def _run_planned_passes(
    *,
    root: Path,
    passes: list,
    rules: list[Rule],
    pack_ids: list[str],
    prompt_prefix: str,
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    raw_dir: Path,
    skip_cache: bool,
    heur_issues: list,
    out_dir: Path | None,
    fmt: str,
    mode: str,
    report_when: object | None,
) -> tuple[
    list[FindingReport],
    dict[str, str],
    dict[str, bool],
    int,
    list[str],
    list[str],
    list[str],
]:
    if not skip_cache:
        from repolens.pipeline.journal import last_finished_label

        last = last_finished_label(root)
        if last:
            prog.detail(f"Resume: last finished pass in journal: {last}")
    parts: list[FindingReport] = []
    raw_by_pass: dict[str, str] = {}
    degraded_by_pass: dict[str, bool] = {}
    repair_attempts_total = 0
    all_coverage_ids: list[str] = []
    finished_labels: list[str] = []
    timed_out_labels: list[str] = []
    prior_summary = ""
    n = len(passes)
    provider = cfg.model.provider or "unknown"
    model_name = cfg.model.model or default_model(cfg.model.provider)
    timeout = resolve_llm_timeout(cfg.model)
    try:
        for idx, deep_pass in enumerate(passes, start=1):
            prefix = prompt_prefix
            if cfg.deep.role_packs and prior_summary:
                block = "## Prior pass findings (compact)\n" + prior_summary
                prefix = f"{prefix}\n\n{block}" if prefix else block
            part, raw, degraded, attempts = run_or_resume_pass(
                root=root,
                idx=idx,
                n=n,
                deep_pass=deep_pass,
                rules=rules,
                pack_ids=pack_ids,
                prompt_prefix=prefix,
                cfg=cfg,
                prog=prog,
                raw_dir=raw_dir,
                model_name=model_name,
                provider=provider,
                timeout=timeout,
                prior_summary=prior_summary if cfg.deep.role_packs else "",
                skip_cache=skip_cache,
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
                    merge_reports(parts, heur_issues),
                    out_dir,
                    fmt,
                    finished_labels,
                    mode,
                    report_when,
                )
            if cfg.deep.role_packs and not degraded:
                from repolens.deep import compact_pass_summary

                prior_summary = compact_pass_summary(part)
    except KeyboardInterrupt:
        raise_aborted(parts, heur_issues, finished_labels, root=root)
    return (
        parts,
        raw_by_pass,
        degraded_by_pass,
        repair_attempts_total,
        all_coverage_ids,
        finished_labels,
        timed_out_labels,
    )
