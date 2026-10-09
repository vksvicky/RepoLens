"""Small review helpers shared by the phase modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repolens.heuristics.runner import HeuristicResult

from pathlib import Path

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
            prog.detail(
                f"SARIF import ({block.tool_name}): "
                f"skipped {block.skipped} result(s)"
            )
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
    state.report = _analyze_deep_passes(
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
    )


def _ollama_status_fn(gen, ollama_base: str | None, use_ollama: bool):
    def status_fn(
        tick=gen,
        base: str | None = ollama_base,
        use: bool = use_ollama,
    ) -> str | None:
        bits = [tick.summary()]
        if use:
            from repolens.provider_status import ollama_running_summary

            live = ollama_running_summary(base)
            if live:
                bits.append(live)
        return " | ".join(bits)

    return status_fn


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

        state.report.issues = apply_fp_calibrations(
            state.report.issues, state.cfg.deep
        )
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
        state.store.record_run(
            started_at=state.started,
            finished_at=time.time(),
            mode=state.mode,
            provider=state.cfg.model.provider,
            model=state.model_name,
            files_in_prompt=len(state.llm_files),
            llm_seconds=None,
            timeout_used=state.timeout,
            outcome="error",
        )
    if isinstance(exc, LlmError) and state.cfg.model.fallback:
        state.prog.phase(
            f"Fallback: LLM error ({exc}) → "
            "degraded to SAST scanners & heuristics"
        )
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


def _record_llm_success(state) -> None:
    import time

    from repolens.adaptive import recommend_timeout

    llm_seconds = time.time() - state.started
    state.llm_seconds_prov = round(time.monotonic() - state._llm_t0, 1)
    if state.store is None:
        return
    state.store.record_run(
        started_at=state.started,
        finished_at=time.time(),
        mode=state.mode,
        provider=state.cfg.model.provider,
        model=state.model_name,
        files_in_prompt=len(state.llm_files),
        llm_seconds=llm_seconds,
        timeout_used=state.timeout,
        outcome="ok",
    )
    hist = state.store.successful_llm_seconds()
    rec = recommend_timeout(
        hist, adaptive=state.cfg.adaptive, file_count=len(state.llm_files)
    )
    state.store.set_meta("recommended_timeout_seconds", f"{rec:g}")


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
    state.graph_issues = cycles_to_issues(
        gres, critical_scc_size=state.cfg.graph.critical_scc_size
    )
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
    from repolens.provenance_attest import (
        git_dirty_tree,
        journal_tip_hash,
        prompt_template_hash,
        scanner_binary_digests,
    )
    from repolens.schema import ProvenanceBlock

    tools = [r.tool for r in state.report.scannerRuns]
    state.report.provenance = ProvenanceBlock(
        repoLensVersion=__version__,
        gitSha=_git_sha(state.root),
        model=state.cfg.model.model,
        provider=state.cfg.model.provider,
        scannerTools=tools,
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
        queueWaitSeconds=round(queue_wait_seconds(), 1),
        dirtyTree=git_dirty_tree(state.root),
        scannerDigests=scanner_binary_digests(tools),
        promptTemplateHash=prompt_template_hash(),
        journalTipHash=journal_tip_hash(state.root),
        notes=list(state.triage_plan.notes) if state.triage_plan is not None else [],
    )


def _apply_verify_and_consistency(state) -> None:
    from repolens.consistency import apply_heuristic_consistency
    from repolens.sarif import verify_issue_location

    for issue in state.report.issues:
        verify_issue_location(state.root, issue)
    if (state.cfg.deep.critical_consistency or "").lower() in {"heuristic", "llm"}:
        state.report.issues = apply_heuristic_consistency(
            state.report.issues, state.cfg.deep
        )
        state.report.summary = state.report.recount_summary()
    if not state.cfg.deep.verify_findings:
        return
    import time

    from repolens.pipeline.journal import append_event
    from repolens.verify_findings import apply_unverified_gate_penalty, apply_verify_findings

    state.prog.detail("Verify findings: Critical/High location + symbol grounding…")
    append_event(state.root, "verify_started")
    verify_started = time.perf_counter()
    state.report.issues = apply_verify_findings(
        state.root, state.report.issues, state.cfg.deep
    )
    state.report = apply_unverified_gate_penalty(state.report)
    state.report.summary = state.report.recount_summary()
    grounded = sum(
        1 for issue in state.report.issues if issue.verificationStatus == "grounded"
    )
    suspect = sum(
        1 for issue in state.report.issues if issue.verificationStatus == "suspect"
    )
    append_event(
        state.root,
        "verify_completed",
        grounded_count=grounded,
        suspect_count=suspect,
        duration_ms=int((time.perf_counter() - verify_started) * 1000),
    )


def _persist_finished_artifacts(state):
    from datetime import UTC, datetime

    from repolens.pipeline.types import ReviewResult
    from repolens.report import write_json_report, write_markdown_report
    from repolens.sarif import write_sarif_report

    if state.report_when is None:
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
        aborted=bool(state.aborted),
    )


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
    _run_scanner_tools(state)
    _postprocess_scanner_issues(state)
    _collect_supply_chain(state)
    _run_fast_brain_phase(state)
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
                _invoke_llm(state)
                if not state.aborted:
                    _merge_llm_report(state)
    _stamp_finished_report(state)
    return _write_finished_report(state)
