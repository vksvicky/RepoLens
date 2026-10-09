"""Merge the model report and write the finished gate files."""

from __future__ import annotations

import time

from repolens.last_llm import (
    save_last_llm_report,
)
from repolens.pipeline.review_state import ReviewRun
from repolens.pipeline.run_support import (
    _apply_verify_and_consistency,
    _attach_complexity,
    _attach_quality,
    _attach_testing,
    _build_finished_provenance,
    _persist_finished_artifacts,
)
from repolens.pipeline.types import ReviewResult
from repolens.triage import (
    stamp_issue_sources,
)


def _merge_llm_report(state: ReviewRun) -> None:
    extra_issues: list = []
    if state.use_deep:
        # Scanners already merged + cross-source deduped in deep_exec.
        if state.graph_issues:
            state.report.issues = list(state.report.issues) + state.graph_issues
            state.report.summary = state.report.recount_summary()
        if state.scanner_runs or state.scanner_gaps:
            state.report.scannerRuns = list(state.scanner_runs)
            state.report.durabilityGaps = list(state.report.durabilityGaps) + list(
                state.scanner_gaps
            )
    else:
        from repolens.deep import is_unmeasured_model_claim

        state.report.issues = [
            issue
            for issue in state.report.issues
            if not is_unmeasured_model_claim(issue)
        ]
        extra_issues = list(state.non_llm_issues)
        if extra_issues or state.scanner_runs or state.scanner_gaps:
            state.report.issues = list(state.report.issues) + extra_issues
            state.report.scannerRuns = list(state.scanner_runs)
            state.report.durabilityGaps = list(state.report.durabilityGaps) + list(
                state.scanner_gaps
            )
            from repolens.scanners.sca import apply_cross_source_sca_dedupe

            state.report = apply_cross_source_sca_dedupe(state.report)
        else:
            state.report.summary = state.report.recount_summary()

    state.report.issues = stamp_issue_sources(state.report.issues, default_llm=True)
    state.report.llmCompleted = True
    state.report.llmSkipped = False
    state.report.llmReusedFrom = None
    if state.triage_plan is not None:
        state.report.triageHits = state.triage_plan.triage_hits
        state.report.llmBypassed = False
    if state.store is not None:
        save_last_llm_report(
            state.store,
            state.report,
            model=state.model_name,
            mode=state.mode,
        )


def _stamp_finished_report(state: ReviewRun) -> None:
    state.report.durationSeconds = round(time.time() - state.run_started, 1)
    if state.graph_block is not None:
        state.report.graph = state.graph_block
    if state.change_set_block is not None:
        state.report.changeSet = state.change_set_block
    if state.graph_gaps:
        state.report.durabilityGaps = list(state.report.durabilityGaps) + [
            g for g in state.graph_gaps if g not in state.report.durabilityGaps
        ]
    if state.supply_chain is not None:
        state.report.supplyChain = state.supply_chain
    if state.inventory_notes:
        state.report.durabilityGaps = list(state.report.durabilityGaps) + [
            n for n in state.inventory_notes if n not in state.report.durabilityGaps
        ]
    from repolens.issue_ids import stamp_issue_ids

    state.report.issues = stamp_issue_ids(stamp_issue_sources(state.report.issues))
    from repolens.cluster import cluster_near_duplicates
    from repolens.feedback_store import apply_feedback_calibrations
    from repolens.suppressions import apply_suppressions

    state.report.issues = apply_feedback_calibrations(
        state.report.issues, state.root, state.cfg.deep
    )
    if state.cfg.deep.cluster_duplicates:
        before_cluster = len(state.report.issues)
        state.report.issues = cluster_near_duplicates(state.report.issues)
        if len(state.report.issues) < before_cluster:
            state.prog.detail(
                f"Clustered {before_cluster - len(state.report.issues)} "
                "near-duplicate finding(s)"
            )
    active, suppressed = apply_suppressions(state.root, state.report.issues)
    state.report.issues = active
    state.report.suppressedIssues = suppressed
    if suppressed:
        state.prog.detail(
            f"Suppressions: {len(suppressed)} finding(s) "
            f"(ignore file / disable comments)"
        )
    state.report.summary = state.report.recount_summary()
    _attach_quality(
        state.report,
        heur_result=state.heur_result,
        files_scanned=state.fast_brain_file_count,
    )


def _write_finished_report(state: ReviewRun) -> ReviewResult:
    from repolens.changeset import tag_findings_for_changeset

    if state.git_diff_requested:
        paths = list(state.git_changed_paths or [])
        tag_findings_for_changeset(state.report.issues, paths)
        tag_findings_for_changeset(
            [row.issue for row in state.report.suppressedIssues],
            paths,
        )
    _attach_complexity(state.report, state.complexity_result)
    _attach_testing(state.report, state.testing_result)
    _build_finished_provenance(state)
    _apply_verify_and_consistency(state)
    return _persist_finished_artifacts(state)
