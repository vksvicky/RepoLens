"""Helpers for deep multi-pass analysis (re-export façade)."""

from __future__ import annotations

from repolens.pipeline.deep_exec_coverage import (
    _apply_coverage_metrics,
    _ordered_unique,
    _phase_coverage_metrics,
    _run_coverage_closure_if_needed,
    _stamp_coverage_and_themes,
)
from repolens.pipeline.deep_exec_merge import (
    _finish_deep_after_passes,
    _fold_scanners,
    _merge_planned_pass_results,
    _pass_outcomes,
    build_pass_confidences_with_floors,
    is_vacuous_llm_report,
)
from repolens.pipeline.deep_exec_plan import (
    _announce_deep_runtime,
    _drive_planned_passes,
    _journal_review_started,
    _load_deep_heuristics,
    _maybe_sync_fts,
    _note_resume_hint,
    _prepare_deep_plan,
    _record_one_planned_pass,
    _sync_adaptive_cache,
)

__all__ = [
    "_announce_deep_runtime",
    "_apply_coverage_metrics",
    "_drive_planned_passes",
    "_finish_deep_after_passes",
    "_fold_scanners",
    "_journal_review_started",
    "_load_deep_heuristics",
    "_maybe_sync_fts",
    "_merge_planned_pass_results",
    "_note_resume_hint",
    "_ordered_unique",
    "_pass_outcomes",
    "_phase_coverage_metrics",
    "_prepare_deep_plan",
    "_record_one_planned_pass",
    "_run_coverage_closure_if_needed",
    "_stamp_coverage_and_themes",
    "_sync_adaptive_cache",
    "build_pass_confidences_with_floors",
    "is_vacuous_llm_report",
]
