"""End-to-end review orchestration."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass
from pathlib import Path

from repolens.adaptive import (
    recommend_timeout,
)
from repolens.config import ModelConfig, RepoLensConfig, load_config
from repolens.llm import LlmError
from repolens.pipeline.deep_exec import (
    _analyze_deep_passes,
)
from repolens.pipeline.prompt import build_prompt
from repolens.pipeline.review_state import ReviewRun
from repolens.pipeline.run_collect import (
    _collect_supply_chain,
    _load_review_inventory,
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
from repolens.pipeline.types import ReviewResult
from repolens.progress import LlmGenerateProgress, ReviewProgress, null_progress
from repolens.schema import (
    FindingReport,
    Summary,
)
from repolens.triage import (
    fail_on_triggered as _fail_on_triggered,
)


def fail_on_triggered(
    report: FindingReport,
    fail_on: str | None,
    *,
    scanner_only: bool = False,
) -> bool:
    """Re-export with Phase 6.3 scanner-only gate support."""
    return _fail_on_triggered(report, fail_on, scanner_only=scanner_only)




def _apply_model_lock(state: ReviewRun) -> None:
    state.cfg.model.lock_cli = state.model_lock
    if state.model_lock is False:
        state.cfg.model.lock = False


def _bind_review_config(state: ReviewRun) -> None:
    if state.force_full and state.force_changed:
        raise ValueError("--full and --changed cannot be combined")
    if state.require_sarif_import and not state.import_sarif:
        raise ValueError(
            "--require-sarif-import needs at least one --import-sarif path"
        )
    if state.git_diff is not None and state.force_full:
        raise ValueError("--full and --git-diff cannot be combined")
    if state.git_diff is not None and state.force_changed:
        raise ValueError("--changed and --git-diff cannot be combined")
    state.prog = state.progress or null_progress()
    state.root = state.path.resolve()
    state.run_started = time.time()
    state.cfg = state.config or load_config(state.root, trust_project=state.trust_project)
    if state.fallback is not None:
        state.cfg.model.fallback = state.fallback
    if state.model_override:
        state.cfg.model.model = state.model_override
    _apply_model_lock(state)
    if state.timeout_override is not None:
        if state.timeout_override <= 0:
            raise ValueError("--timeout must be a positive number of seconds")
        state.cfg.model.timeout_seconds = state.timeout_override
    if state.deep_passes is not None:
        if state.deep_passes < 1:
            raise ValueError("--deep-passes must be >= 1")
        state.cfg.deep.max_passes = state.deep_passes
    if state.verify_findings is True:
        state.cfg.deep.verify_findings = True
    elif state.verify_findings is False:
        state.cfg.deep.verify_findings = False
    from repolens.packs.registry import resolve_enabled_packs

    state.pack_ids = resolve_enabled_packs([*state.cfg.packs.enabled, *(state.packs or [])])
    state.cfg.packs.enabled = list(state.pack_ids)

    state.change_set_block = None
    state.git_diff_requested = state.git_diff is not None






def _invoke_llm(state: ReviewRun) -> None:
    from repolens.pipeline.interrupt import InterruptGuard

    with InterruptGuard():
        _invoke_llm_body(state)


def _invoke_llm_body(state: ReviewRun) -> None:
    try:
        if state.use_deep:
            from datetime import UTC, datetime

            if state.report_when is None:
                state.report_when = datetime.now(UTC)
            # Per-pass waiting lives inside _analyze_deep_passes.
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
            )
        else:
            gen = LlmGenerateProgress()
            ollama_base = (
                state.cfg.model.base_url if state.provider == "ollama" else None
            )

            def status_fn(
                tick: LlmGenerateProgress = gen,
                base: str | None = ollama_base,
                use_ollama: bool = state.provider == "ollama",
            ) -> str | None:
                bits = [tick.summary()]
                if use_ollama:
                    from repolens.provider_status import (
                        ollama_running_summary,
                    )

                    live = ollama_running_summary(base)
                    if live:
                        bits.append(live)
                return " | ".join(bits)

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
    except BaseException as exc:
        from repolens.pipeline.types import ReviewAborted

        if isinstance(exc, ReviewAborted):
            state.report = exc.report
            state.aborted = True
            return
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
        else:
            raise
    else:
        llm_seconds = time.time() - state.started
        state.llm_seconds_prov = round(time.monotonic() - state._llm_t0, 1)
        if state.store is not None:
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





def run_review(
    *,
    path: Path,
    mode: str,
    review_mode: str = "full",
    since: str | None = None,
    out_dir: Path | None = None,
    fmt: str = "md",
    model_override: str | None = None,
    timeout_override: float | None = None,
    force_full: bool = False,
    force_changed: bool = False,
    git_diff: str | None = None,
    deep_passes: int | None = None,
    full_audit: bool = False,
    dry_run: bool = False,
    trust_project: bool = False,
    config: RepoLensConfig | None = None,
    scanners: str | None = "auto",
    require_scanners: bool = False,
    scanners_only: bool = False,
    progress: ReviewProgress | None = None,
    deep: bool | None = None,
    ci: bool = False,
    sarif: bool = False,
    verify_findings: bool | None = None,
    packs: list[str] | None = None,
    fallback: bool | None = None,
    import_sarif: list[Path] | None = None,
    require_sarif_import: bool = False,
    model_lock: bool | None = None,
    resume: bool = True,
) -> ReviewResult:

    state = ReviewRun(
        path=path,
        mode=mode,
        review_mode=review_mode,
        since=since,
        out_dir=out_dir,
        fmt=fmt,
        model_override=model_override,
        timeout_override=timeout_override,
        force_full=force_full,
        force_changed=force_changed,
        git_diff=git_diff,
        deep_passes=deep_passes,
        full_audit=full_audit,
        dry_run=dry_run,
        trust_project=trust_project,
        config=config,
        scanners=scanners,
        require_scanners=require_scanners,
        scanners_only=scanners_only,
        progress=progress,
        deep=deep,
        ci=ci,
        sarif=sarif,
        verify_findings=verify_findings,
        packs=packs,
        fallback=fallback,
        import_sarif=import_sarif,
        require_sarif_import=require_sarif_import,
        model_lock=model_lock,
        resume=resume,
    )
    _bind_review_config(state)
    _load_review_inventory(state)
    try:
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
    finally:
        if state.store is not None:
            state.store.close()


def _analyze_with_repair(
    prompt: str,
    model_cfg: ModelConfig,
    *,
    progress: ReviewProgress | None = None,
    root: Path | None = None,
    on_delta: Callable[[str], None] | None = None,
) -> FindingReport:
    from repolens.llm_structured import analyze_structured

    prog = progress or null_progress()
    raw_dir = (root / ".repolens") if root is not None else None
    result = analyze_structured(
        prompt,
        model_cfg,
        pass_id="single",
        progress=prog,
        raw_dir=raw_dir,
        on_delta=on_delta,
    )
    if result.layer == "degraded":
        prog.phase(
            "LLM: output degraded — report still written (scanners/heuristics/partial)"
        )
    if result.report is None:
        return FindingReport(
            confidence=0,
            summary=Summary(),
            issues=[],
            durabilityGaps=["LLM returned None"],
            llmRepairAttempts=result.repair_attempts or None,
        )
    if result.repair_attempts:
        result.report.llmRepairAttempts = result.repair_attempts
    return result.report



