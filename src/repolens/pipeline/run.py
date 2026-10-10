"""End-to-end review orchestration."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from repolens.config import ModelConfig, RepoLensConfig, load_config
from repolens.pipeline.review_state import ReviewRun
from repolens.pipeline.run_collect import _load_review_inventory
from repolens.pipeline.run_support import (
    _execute_review_body,
    _handle_llm_invoke_error,
    _invoke_deep_llm,
    _invoke_single_llm,
    _record_llm_success,
)
from repolens.pipeline.types import ReviewResult
from repolens.progress import ReviewProgress, null_progress
from repolens.schema import FindingReport, Summary
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


def _apply_deep_cli_overrides(state: ReviewRun) -> None:
    if state.deep_passes is not None:
        if state.deep_passes < 1:
            raise ValueError("--deep-passes must be >= 1")
        state.cfg.deep.max_passes = state.deep_passes
    if state.verify_findings is True:
        state.cfg.deep.verify_findings = True
    elif state.verify_findings is False:
        state.cfg.deep.verify_findings = False
    if state.role_packs is True:
        state.cfg.deep.role_packs = True
    elif state.role_packs is False:
        state.cfg.deep.role_packs = False


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
    _apply_deep_cli_overrides(state)
    from repolens.packs.registry import resolve_enabled_packs

    state.pack_ids = resolve_enabled_packs(
        [*state.cfg.packs.resolved(), *(state.packs or [])]
    )
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
            _invoke_deep_llm(state)
        else:
            _invoke_single_llm(state)
    except BaseException as exc:
        if _handle_llm_invoke_error(state, exc):
            return
    else:
        _record_llm_success(state)


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
    role_packs: bool | None = None,
    retry_passes: list[str] | None = None,
    invoked_command: str | None = None,
    expanded_argv: list[str] | None = None,
) -> ReviewResult:
    expanded_argv = list(expanded_argv or [])
    state = ReviewRun(**locals())
    _bind_review_config(state)
    _load_review_inventory(state)
    try:
        return _execute_review_body(state)
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
