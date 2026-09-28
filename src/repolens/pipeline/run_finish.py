"""Merge the model report and write the finished gate files."""

from __future__ import annotations

import time
from datetime import UTC

from repolens.last_llm import (
    save_last_llm_report,
)
from repolens.pipeline.review_state import ReviewRun
from repolens.pipeline.run_support import (
    _attach_complexity,
    _attach_quality,
    _attach_testing,
    _git_sha,
)
from repolens.pipeline.types import ReviewResult
from repolens.report import write_json_report, write_markdown_report
from repolens.schema import (
    ProvenanceBlock,
)
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
    from repolens import __version__

    _attach_complexity(state.report, state.complexity_result)
    _attach_testing(state.report, state.testing_result)
    state.report.provenance = ProvenanceBlock(
        repoLensVersion=__version__,
        gitSha=_git_sha(state.root),
        model=state.cfg.model.model,
        provider=state.cfg.model.provider,
        scannerTools=[r.tool for r in state.report.scannerRuns],
        triageRouting=state.cfg.ci.triage_routing,
        llmBypassed=bool(state.report.llmBypassed),
        triageHits=int(state.report.triageHits or 0),
        failOnScannerOnly=bool(
            state.cfg.ci.triage_routing and state.cfg.ci.fail_on_scanner_only
        ),
        fastBrainFiles=state.fast_brain_file_count,
        llmPackFiles=state.llm_pack_file_count,
        fastBrainSeconds=state.fast_brain_seconds,
        llmSeconds=state.llm_seconds_prov,
        notes=list(state.triage_plan.notes) if state.triage_plan is not None else [],
    )
    # Phase 6.4: stamp locationVerified before Markdown/SARIF write
    from repolens.sarif import verify_issue_location, write_sarif_report

    for issue in state.report.issues:
        verify_issue_location(state.root, issue)
    from repolens.consistency import apply_heuristic_consistency

    if (state.cfg.deep.critical_consistency or "").lower() in {"heuristic", "llm"}:
        state.report.issues = apply_heuristic_consistency(state.report.issues, state.cfg.deep)
        state.report.summary = state.report.recount_summary()
    from repolens.verify_findings import apply_verify_findings

    if state.cfg.deep.verify_findings:
        state.prog.detail("Verify findings: re-checking Critical locations (non-fatal)…")
        state.report.issues = apply_verify_findings(state.root, state.report.issues, state.cfg.deep)
        state.report.summary = state.report.recount_summary()

    from datetime import datetime

    state.report_when = datetime.now(UTC)
    state.prog.phase(f"Writing report → {state.out}")
    state.md = (
        write_markdown_report(state.report, state.out, mode=state.mode, when=state.report_when)
        if state.fmt in {"md", "both"}
        else None
    )
    state.js = (
        write_json_report(state.report, state.out, mode=state.mode, when=state.report_when)
        if state.fmt in {"json", "both"}
        else None
    )
    if state.js is not None:
        from repolens.explain import write_last_report_pointer

        write_last_report_pointer(state.root, state.js)
    elif state.md is not None and state.fmt == "md":
        # Prefer JSON for explain; when md-only, still write JSON sidecar for lookup.
        state.js = write_json_report(
            state.report, state.out, mode=state.mode, when=state.report_when
        )
        from repolens.explain import write_last_report_pointer

        write_last_report_pointer(state.root, state.js)
    sarif_path = None
    if state.sarif:
        sarif_path = write_sarif_report(
            state.report, state.root, out_dir=state.out, mode=state.mode, when=state.report_when
        )
        if sarif_path is not None:
            n = sum(1 for i in state.report.issues if i.locationVerified)
            state.prog.detail(
                f"SARIF: {sarif_path.name} "
                f"({n}/{len(state.report.issues)} location-verified result(s))"
            )
    state.prog.phase("Done")
    return ReviewResult(
        report=state.report,
        markdown_path=state.md,
        json_path=state.js,
        files_scanned=state.fast_brain_file_count,
        dry_run=False,
        sarif_path=sarif_path,
    )
