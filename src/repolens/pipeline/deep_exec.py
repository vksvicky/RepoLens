"""Deep multi-pass analysis and coverage metric application."""

from __future__ import annotations

from pathlib import Path

from repolens.config import RepoLensConfig
from repolens.heuristics import HeuristicResult
from repolens.inventory import FileEntry
from repolens.pipeline.deep_exec_support import (  # noqa: F401 — re-export for callers
    _announce_deep_runtime,
    _apply_coverage_metrics,
    _drive_planned_passes,
    _finish_deep_after_passes,
    _fold_scanners,
    _journal_review_started,
    _load_deep_heuristics,
    _maybe_sync_fts,
    _merge_planned_pass_results,
    _note_resume_hint,
    _ordered_unique,
    _pass_outcomes,
    _phase_coverage_metrics,
    _prepare_deep_plan,
    _record_one_planned_pass,
    _run_coverage_closure_if_needed,
    _stamp_coverage_and_themes,
    _sync_adaptive_cache,
    build_pass_confidences_with_floors,
    is_vacuous_llm_report,
)
from repolens.pipeline.deep_pass import (
    _ollama_wait_bits as _ollama_wait_bits,
)
from repolens.pipeline.deep_pass import (
    _pass_report as _pass_report,
)
from repolens.pipeline.pass_resume import raise_aborted
from repolens.progress import ReviewProgress
from repolens.rules.registry import Rule
from repolens.schema import FindingReport


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
    retry_passes: frozenset[str] = frozenset(),
) -> FindingReport:
    """Heuristics → plan passes → structured LLM per pass → merge + coverage."""
    _journal_review_started(root, cfg)
    heur, rules, passes, p3_gaps, pack_ids = _prepare_deep_plan(
        root=root,
        mode=mode,
        full_audit=full_audit,
        files=files,
        llm_files=llm_files,
        cfg=cfg,
        prog=prog,
        heur_result=heur_result,
        graph=graph,
    )
    _announce_deep_runtime(prog, passes, cfg)
    raw_dir = root / ".repolens"
    planned = _run_planned_passes(
        root=root,
        passes=passes,
        rules=rules,
        pack_ids=pack_ids,
        prompt_prefix=prompt_prefix,
        cfg=cfg,
        prog=prog,
        raw_dir=raw_dir,
        skip_cache=skip_cache,
        retry_passes=retry_passes,
        heur_issues=heur.issues,
        out_dir=out_dir,
        fmt=fmt,
        mode=mode,
        report_when=report_when,
    )
    parts, raw_by_pass, degraded_by_pass, repairs, ids, finished, timed_out = planned
    return _finish_deep_after_passes(
        root=root,
        mode=mode,
        full_audit=full_audit,
        files=files,
        llm_files=llm_files,
        cfg=cfg,
        prog=prog,
        scanner_runs=scanner_runs,
        scanner_issues=scanner_issues,
        passes=passes,
        parts=parts,
        raw_by_pass=raw_by_pass,
        degraded_by_pass=degraded_by_pass,
        repair_attempts_total=repairs,
        all_coverage_ids=ids,
        finished_labels=finished,
        timed_out_labels=timed_out,
        heur_issues=heur.issues,
        p3_gaps=p3_gaps,
        raw_dir=raw_dir,
        out_dir=out_dir,
        fmt=fmt,
        report_when=report_when,
    )


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
    retry_passes: frozenset[str] = frozenset(),
) -> tuple[
    list[FindingReport],
    dict[str, str],
    dict[str, bool],
    int,
    list[str],
    list[str],
    list[str],
]:
    _note_resume_hint(root, skip_cache, prog)
    parts: list[FindingReport] = []
    raw_by_pass: dict[str, str] = {}
    degraded_by_pass: dict[str, bool] = {}
    all_coverage_ids: list[str] = []
    finished_labels: list[str] = []
    timed_out_labels: list[str] = []
    try:
        repairs = _drive_planned_passes(
            root=root,
            passes=passes,
            rules=rules,
            pack_ids=pack_ids,
            prompt_prefix=prompt_prefix,
            cfg=cfg,
            prog=prog,
            raw_dir=raw_dir,
            skip_cache=skip_cache,
            heur_issues=heur_issues,
            out_dir=out_dir,
            fmt=fmt,
            mode=mode,
            report_when=report_when,
            parts=parts,
            raw_by_pass=raw_by_pass,
            degraded_by_pass=degraded_by_pass,
            all_coverage_ids=all_coverage_ids,
            finished_labels=finished_labels,
            timed_out_labels=timed_out_labels,
            retry_passes=retry_passes,
        )
    except KeyboardInterrupt:
        raise_aborted(parts, heur_issues, finished_labels, root=root)
    return (
        parts,
        raw_by_pass,
        degraded_by_pass,
        repairs,
        all_coverage_ids,
        finished_labels,
        timed_out_labels,
    )
