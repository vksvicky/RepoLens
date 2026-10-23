"""Small review helpers shared by the phase modules."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from repolens.pipeline.deep_job import DeepJob

if TYPE_CHECKING:
    from repolens.heuristics.runner import HeuristicResult

from pathlib import Path

from repolens.learning.store import RecordRun
from repolens.progress import ReviewProgress
from repolens.schema import (
    FindingReport,
)


def _attach_quality(
    report: FindingReport,
    *,
    heur_result: HeuristicResult | None,
    files_scanned: int,
) -> None:
    from repolens.quality import build_quality_scorecard_from_issues

    if files_scanned <= 0 or heur_result is None:
        return
    report.quality = build_quality_scorecard_from_issues(
        report.issues,
        near_clone_clusters=heur_result.near_clone_clusters,
        near_clone_occurrences=heur_result.near_clone_occurrences,
        files_scanned=files_scanned,
        notes=list(heur_result.near_clone_notes),
    )


def _attach_complexity(report: FindingReport, complexity_result) -> None:
    if complexity_result is None:
        return
    report.complexity = complexity_result.block


def _attach_testing(report: FindingReport, testing_result) -> None:
    if testing_result is None:
        return
    report.testing = testing_result.block


def _complexity_ai_prefix(root: Path, complexity_result, cfg) -> str:
    if complexity_result is None or not cfg.complexity.enabled:
        return ""
    from repolens.complexity.ai_pack import (
        format_complexity_ai_section,
        select_complexity_ai_targets,
    )

    targets = select_complexity_ai_targets(
        complexity_result.functions,
        top_n=cfg.complexity.top_n_ai_explanations,
    )
    return format_complexity_ai_section(root, targets)


def _extend_from_import_sarif(
    import_sarif: list[Path] | None,
    root: Path,
    scanner_issues: list,
    scanner_runs: list,
    prog: ReviewProgress,
    *,
    require: bool = False,
) -> None:
    if not import_sarif:
        return
    from repolens.sarif_import import load_many_sarif, scanner_runs_from_imports

    imported = load_many_sarif(list(import_sarif), root=root, require=require)
    for block in imported:
        scanner_issues.extend(block.issues)
        if block.skipped:
            prog.detail(f"SARIF import ({block.tool_name}): skipped {block.skipped} result(s)")
    scanner_runs.extend(scanner_runs_from_imports(imported))


def _git_sha(root: Path) -> str | None:
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        logging.getLogger(__name__).debug("handled expected error", exc_info=True)
        return None
    if completed.returncode != 0:
        return None
    sha = (completed.stdout or "").strip()
    return sha or None


def _invoke_deep_llm(state) -> None:
    from datetime import UTC, datetime

    from repolens.pipeline.deep_exec import _analyze_deep_passes
    from repolens.pipeline.pass_cache import normalize_retry_passes

    if state.report_when is None:
        state.report_when = datetime.now(UTC)
    from repolens.pipeline.pass_timing import close_pass_timings, open_pass_timings

    token = open_pass_timings()
    try:
        state.report = _analyze_deep_passes(DeepJob(
        root=state.root,
        mode=state.mode,
        full_audit=state.full_audit,
        files=state.fast_files,
        llm_files=state.llm_files,
        cfg=state.cfg,
        prog=state.prog,
        prompt_prefix=state.prompt_prefix,
        scanner_runs=state.scanner_runs,
        scanner_issues=list(state.scanner_issues),
        heur_result=state.heur_result,
        out_dir=state.out,
        fmt=state.fmt,
        report_when=state.report_when,
        skip_cache=not bool(state.resume),
        retry_passes=normalize_retry_passes(state.retry_passes),
        graph=state.graph_result,
        change_set=state.change_set_block,
        ))
    finally:
        state.pass_timings = close_pass_timings(token)


def _status_with_ollama(gen, ollama_base: str | None):
    def status_fn(tick=gen, base: str | None = ollama_base) -> str | None:
        from repolens.provider_status import ollama_running_summary

        bits = [tick.summary()]
        live = ollama_running_summary(base)
        if live:
            bits.append(live)
        return " | ".join(bits)

    return status_fn


def _status_without_ollama(gen):
    def status_fn(tick=gen) -> str | None:
        return tick.summary()

    return status_fn


def _ollama_status_fn(gen, ollama_base: str | None, use_ollama: bool):
    return (
        _status_with_ollama(gen, ollama_base)
        if use_ollama
        else _status_without_ollama(gen)
    )


def _invoke_single_llm(state) -> None:
    from repolens.pipeline.prompt import build_prompt
    from repolens.progress import LlmGenerateProgress

    gen = LlmGenerateProgress()
    ollama_base = state.cfg.model.base_url if state.provider == "ollama" else None
    status_fn = _ollama_status_fn(gen, ollama_base, state.provider == "ollama")
    with state.prog.waiting(
        state.llm_label,
        hint="streaming chat completions",
        status_fn=status_fn,
    ):
        state.prog.phase("Building LLM prompt…")
        prompt = build_prompt(
            state.mode,
            state.root,
            state.llm_files,
            full_audit=state.full_audit,
            pack_ids=state.pack_ids,
        )
        if state.prompt_prefix:
            prompt = state.prompt_prefix + "\n\n" + prompt
        state.prog.detail(f"prompt size ≈ {len(prompt):,} characters")
        from repolens.pipeline.run import _analyze_with_repair

        state.report = _analyze_with_repair(
            prompt,
            state.cfg.model,
            progress=state.prog,
            root=state.root,
            on_delta=gen.note_delta,
        )
        from repolens.consistency import apply_llm_consistency
        from repolens.fp_calibrations import apply_fp_calibrations

        state.report.issues = apply_fp_calibrations(state.report.issues, state.cfg.deep)
        if (state.cfg.deep.critical_consistency or "").lower() == "llm":
            state.prog.phase("Critical consistency (LLM confirm)…")
            state.report.issues = apply_llm_consistency(
                state.report.issues, state.cfg.deep, state.cfg.model
            )
        state.report.summary = state.report.recount_summary()
    gen.mark_done()


def _handle_llm_invoke_error(state, exc: BaseException) -> bool:
    """Return True when the exception was handled (caller should return)."""
    import time

    from repolens.llm import LlmError
    from repolens.pipeline.types import ReviewAborted
    from repolens.schema import FindingReport, Summary

    if isinstance(exc, ReviewAborted):
        state.report = exc.report
        state.aborted = True
        return True
    if state.store is not None:
        state.store.record_run(RecordRun(
        started_at=state.started,
        finished_at=time.time(),
        mode=state.mode,
        provider=state.cfg.model.provider,
        model=state.model_name,
        files_in_prompt=len(state.llm_files),
        llm_seconds=None,
        timeout_used=state.timeout,
        outcome="error",
    ))
    if isinstance(exc, LlmError) and state.cfg.model.fallback:
        state.prog.phase(f"Fallback: LLM error ({exc}) → degraded to SAST scanners & heuristics")
        state.report = FindingReport(
            confidence=55,
            summary=Summary(),
            issues=state.non_llm_issues,
            durabilityGaps=[
                f"Fallback: LLM execution failed ({exc}); "
                "report generated using local scanners and "
                "Fast-Brain heuristics."
            ]
            + list(state.scanner_gaps),
            scannerRuns=list(state.scanner_runs),
            supplyChain=state.supply_chain,
            llmSkipped=True,
        )
        state.report.summary = state.report.recount_summary()
        return True
    raise exc


def _run_graph_phase(state) -> None:
    from pathlib import Path

    from repolens.schema import GraphBlock

    state.graph_issues = []
    state.graph_block = None
    state.graph_gaps = []
    state.graph_result = None
    if not any(Path(f.relative).suffix == ".py" for f in state.fast_files):
        return
    from repolens.graph import analyse_repo_graph
    from repolens.graph.findings import cycles_to_issues

    gres = analyse_repo_graph(state.root, config=state.cfg.graph)
    state.graph_result = gres
    state.graph_gaps = list(gres.durability_gaps)
    state.graph_issues = cycles_to_issues(gres, critical_scc_size=state.cfg.graph.critical_scc_size)
    state.graph_block = GraphBlock(
        status=gres.status.value,
        cyclicity=gres.cyclicity,
        cycleCount=len(gres.cycles),
        moduleCount=gres.module_count,
        packageCount=len(gres.packages),
    )
    state.prog.detail(
        f"Import graph: {state.graph_block.cycleCount} cycle group(s), "
        f"{len(state.graph_issues)} finding(s), cyclicity={state.graph_block.cyclicity}"
    )


def _build_finished_provenance(state):
    from repolens import __version__
    from repolens.llm.model_lock import queue_wait_seconds
    from repolens.memory_sample import PYTHON_RSS_NOTE, read_peak_rss_bytes
    from repolens.provenance_attest import (
        git_branch,
        git_dirty_tree,
        journal_tip_hash,
        prompt_template_hash,
        scanner_binary_digests,
    )
    from repolens.schema import ProvenanceBlock

    tools = [r.tool for r in state.report.scannerRuns]
    state.report.provenance = ProvenanceBlock(
        repoLensVersion=__version__,
        reviewedPath=str(state.root),
        gitSha=_git_sha(state.root),
        gitBranch=git_branch(state.root),
        model=state.cfg.model.model,
        provider=state.cfg.model.provider,
        scannerTools=tools,
        triageRouting=state.cfg.ci.triage_routing,
        llmBypassed=bool(state.report.llmBypassed),
        triageHits=int(state.report.triageHits or 0),
        failOnScannerOnly=bool(state.cfg.ci.triage_routing and state.cfg.ci.fail_on_scanner_only),
        fastBrainFiles=state.fast_brain_file_count,
        llmPackFiles=state.llm_pack_file_count,
        fastBrainSeconds=state.fast_brain_seconds,
        llmSeconds=state.llm_seconds_prov,
        queueWaitSeconds=round(queue_wait_seconds(), 1),
        dirtyTree=git_dirty_tree(state.root),
        scannerDigests=scanner_binary_digests(tools),
        promptTemplateHash=prompt_template_hash(),
        journalTipHash=journal_tip_hash(state.root),
        notes=list(state.triage_plan.notes) if state.triage_plan is not None else [],
        command=state.invoked_command,
        expandedArgv=list(state.expanded_argv or []),
        pythonPeakRssBytes=read_peak_rss_bytes(),
        pythonRssNote=PYTHON_RSS_NOTE,
        passTimings=list(state.pass_timings or []),
    )


def _apply_verify_and_consistency(state) -> None:
    from repolens.consistency import apply_heuristic_consistency
    from repolens.sarif import verify_issue_location

    for issue in state.report.issues:
        verify_issue_location(state.root, issue)
    if (state.cfg.deep.critical_consistency or "").lower() in {"heuristic", "llm"}:
        state.report.issues = apply_heuristic_consistency(state.report.issues, state.cfg.deep)
        state.report.summary = state.report.recount_summary()
    if not state.cfg.deep.verify_findings:
        return
    import time

    from repolens.pipeline.journal import append_event
    from repolens.verify_findings import apply_unverified_gate_penalty, apply_verify_findings

    state.prog.detail("Verify findings: Critical/High location + symbol grounding…")
    append_event(state.root, "verify_started")
    verify_started = time.perf_counter()
    state.report.issues = apply_verify_findings(state.root, state.report.issues, state.cfg.deep)
    state.report = apply_unverified_gate_penalty(state.report)
    state.report.summary = state.report.recount_summary()
    grounded = sum(1 for issue in state.report.issues if issue.verificationStatus == "grounded")
    suspect = sum(1 for issue in state.report.issues if issue.verificationStatus == "suspect")
    append_event(
        state.root,
        "verify_completed",
        grounded_count=grounded,
        suspect_count=suspect,
        duration_ms=int((time.perf_counter() - verify_started) * 1000),
    )


def _advise_local_32b(state) -> None:
    from repolens.memory_sample import local_32b_notice, physical_ram_bytes

    notice = local_32b_notice(
        state.cfg.model.provider,
        state.cfg.model.model,
        physical_ram_bytes(),
    )
    if notice:
        state.prog.phase(notice)


def _enforce_memory_ceiling(state) -> None:
    from repolens.memory_sample import bytes_for_ceiling, ceiling_decision
    from repolens.pipeline.types import MemoryCeilingError

    hint, stop = ceiling_decision(
        state.cfg.model.memory_ceiling_mb,
        bytes_for_ceiling(),
        state.cfg.model.memory_abort,
    )
    if hint:
        state.prog.phase(hint)
    if stop:
        raise MemoryCeilingError(hint or "memory ceiling")


def _overlap_scanners_and_fast_brain(state, *, postprocess, supply, fast_brain) -> None:
    """Run scanner postprocess and Fast Brain together.

    Supply chain starts only after the scanner call returns, so a second Trivy
    does not share the pool with the first. Both sides are joined before the
    caller continues. An error on one side waits for the other, then surfaces
    on this thread.
    """
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="repolens-fast-brain") as pool:
        fast_future = pool.submit(fast_brain, state)
        scanner_error: BaseException | None = None
        try:
            postprocess(state)
            supply(state)
        except BaseException as exc:
            scanner_error = exc
        fast_error: BaseException | None = None
        try:
            fast_future.result()
        except BaseException as exc:
            fast_error = exc
    if scanner_error is not None:
        raise scanner_error
    if fast_error is not None:
        raise fast_error


def _execute_review_body(state):
    from repolens.pipeline.run import _invoke_llm
    from repolens.pipeline.run_collect import (
        _collect_supply_chain,
        _postprocess_scanner_issues,
        _run_fast_brain_phase,
        _run_scanner_tools,
        _write_dry_run,
    )
    from repolens.pipeline.run_finish import (
        _merge_llm_report,
        _stamp_finished_report,
        _write_finished_report,
    )
    from repolens.pipeline.run_route import (
        _apply_git_diff_scope,
        _apply_provider_fallback,
        _apply_triage_routing,
        _prepare_llm_prompt,
        _report_empty_inventory,
        _report_scanners_only,
        _reuse_or_skip_llm,
        _select_adaptive_pack,
    )

    if state.dry_run:
        return _write_dry_run(state)
    _advise_local_32b(state)
    _run_scanner_tools(state)
    _overlap_scanners_and_fast_brain(
        state,
        postprocess=_postprocess_scanner_issues,
        supply=_collect_supply_chain,
        fast_brain=_run_fast_brain_phase,
    )
    _apply_provider_fallback(state)
    if state.scanners_only:
        _report_scanners_only(state)
    elif not state.files and not state.fast_files:
        _report_empty_inventory(state)
    else:
        _select_adaptive_pack(state)
        _apply_git_diff_scope(state)
        _apply_triage_routing(state)
        if not state.triage_bypassed:
            if not state.llm_files:
                _reuse_or_skip_llm(state)
            else:
                _prepare_llm_prompt(state)
                _enforce_memory_ceiling(state)
                _invoke_llm(state)
                if not state.aborted:
                    _merge_llm_report(state)
    _stamp_finished_report(state)
    return _write_finished_report(state)
