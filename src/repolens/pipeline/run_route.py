"""Provider fallback, pack selection, and LLM prompt prep."""

from __future__ import annotations

import time

from repolens.adaptive import (
    recommend_timeout,
    resolve_effective_timeout,
    select_pack_paths,
)
from repolens.last_llm import (
    bootstrap_from_out_dir,
    load_last_llm_report,
    merge_reused_report,
    save_last_llm_report,
)
from repolens.llm import default_model, resolve_llm_timeout
from repolens.pipeline.deep_exec import (
    _maybe_sync_fts,
)
from repolens.pipeline.review_state import ReviewRun
from repolens.pipeline.run_support import _complexity_ai_prefix, _extend_from_import_sarif
from repolens.scanners.runner import run_scanners
from repolens.scanners.sca import dedupe_sca_issues
from repolens.schema import (
    FindingReport,
    Summary,
)
from repolens.triage import (
    select_pack_entries,
    triage_llm_plan,
)


def _non_llm_issues(state: ReviewRun) -> list:
    return (
        list(state.scanner_issues)
        + state.heur_issues
        + state.complexity_issues
        + state.graph_issues
    )


def _provider_has_key(state: ReviewRun) -> bool:
    from repolens.config import resolve_api_key

    state.provider = state.cfg.model.provider
    if not state.provider:
        return False
    if state.provider in {"openai", "anthropic", "deepseek", "openai_compatible"}:
        return bool(resolve_api_key(state.cfg.model))
    return True


def _switch_fallback_to_ollama(state: ReviewRun) -> None:
    from repolens.llm.setup import resolve_ollama_model

    chosen, _ = resolve_ollama_model(state.cfg.model.model)
    state.cfg.model.provider = "ollama"
    state.cfg.model.model = chosen
    state.prog.phase(
        f"Fallback: Cloud AI key missing → switching to local Ollama ({chosen})"
    )


def _run_fallback_scanners(state: ReviewRun) -> bool:
    if state.tools:
        return False
    state.tools = list(state.cfg.scanners.enabled)
    if not state.tools:
        return False
    state.prog.phase(f"Scanners: running {', '.join(state.tools)}…")
    state.scanner_runs, state.scanner_issues, state.scanner_gaps = run_scanners(
        state.root, state.tools
    )
    _extend_from_import_sarif(
        state.import_sarif,
        state.root,
        state.scanner_issues,
        state.scanner_runs,
        state.prog,
        require=state.require_sarif_import,
    )
    before_dedupe = len(state.scanner_issues)
    state.scanner_issues = dedupe_sca_issues(state.scanner_issues)
    if len(state.scanner_issues) < before_dedupe:
        state.prog.detail(
            f"SCA: deduped {before_dedupe - len(state.scanner_issues)} "
            "duplicate OSV/Trivy advisory row(s)"
        )
    return True


def _degrade_without_llm(state: ReviewRun) -> bool:
    state.scanners_only = True
    refreshed = _run_fallback_scanners(state)
    state.prog.phase(
        "Fallback: Cloud AI key & Ollama unavailable → "
        "degraded to SAST scanners & heuristics"
    )
    state.scanner_gaps.insert(
        0,
        "Fallback: Cloud AI key & Ollama unavailable; "
        "report generated using local scanners and "
        "Fast-Brain heuristics.",
    )
    return refreshed


def _apply_provider_fallback(state: ReviewRun) -> None:
    state.non_llm_issues = _non_llm_issues(state)
    refreshed = False
    if not state.scanners_only and not state.dry_run and state.cfg.model.fallback:
        from repolens.llm.setup import detect_ollama

        if not _provider_has_key(state):
            if detect_ollama():
                _switch_fallback_to_ollama(state)
            else:
                refreshed = _degrade_without_llm(state)
    if refreshed:
        state.non_llm_issues = _non_llm_issues(state)


def _report_scanners_only(state: ReviewRun) -> None:
    all_ran = bool(state.scanner_runs) and all(r.status == "ran" for r in state.scanner_runs)
    state.report = FindingReport(
        confidence=75 if all_ran else 55,
        summary=Summary(),
        issues=state.non_llm_issues,
        durabilityGaps=list(state.scanner_gaps)
        or (
            ["scanners-only: no scanners selected"]
            if not state.tools and not state.import_sarif
            else []
        ),
        scannerRuns=list(state.scanner_runs),
        supplyChain=state.supply_chain,
        llmSkipped=True,
    )
    from repolens.scanners.sca import apply_cross_source_sca_dedupe

    state.report = apply_cross_source_sca_dedupe(state.report)


def _report_empty_inventory(state: ReviewRun) -> None:
    state.report = FindingReport(
        confidence=90,
        summary=Summary(),
        issues=state.non_llm_issues,
        durabilityGaps=["No reviewable files found (check ignores / --mode diff)"]
        + state.scanner_gaps,
        scannerRuns=list(state.scanner_runs),
        supplyChain=state.supply_chain,
    )
    from repolens.scanners.sca import apply_cross_source_sca_dedupe

    state.report = apply_cross_source_sca_dedupe(state.report)


def _select_adaptive_pack(state: ReviewRun) -> None:
    if state.force_changed:
        state.pack_mode = "changed"
    elif state.force_full:
        state.pack_mode = "full"
    else:
        state.pack_mode = state.cfg.adaptive.mode
    state.llm_files = state.files
    if state.store is not None and state.diff is not None and state.cfg.adaptive.enabled:
        state.llm_files = select_pack_paths(state.files, state.diff, mode=state.pack_mode)
        delta_n = len(state.diff.added) + len(state.diff.changed)
        note = ""
        if (
            state.pack_mode == "auto"
            and delta_n == 0
            and len(state.llm_files) == len(state.files)
            and state.files
        ):
            note = (
                " — no fingerprint delta → full pack "
                "(use --changed for delta-only smoke)"
            )
        state.prog.phase(
            f"LLM pack: {len(state.llm_files)}/{len(state.files)} file(s) "
            f"(adaptive mode={state.pack_mode}){note}"
        )


def _apply_git_diff_scope(state: ReviewRun) -> None:
    if state.git_diff_requested:
        from repolens.changeset import (
            cap_changeset_paths,
            filter_entries_to_changeset,
            list_git_changed_paths,
        )
        from repolens.git_refs import resolve_diff_base
        from repolens.schema import ChangeSetBlock

        resolved_base = resolve_diff_base(
            cli_base=state.git_diff_base_cli, cwd=state.root
        )
        state.git_changed_paths = list_git_changed_paths(
            state.root, resolved_base, include_dirty=True
        )
        state.llm_files = filter_entries_to_changeset(state.llm_files, state.git_changed_paths)
        state.change_set_block = ChangeSetBlock(
            base=resolved_base,
            pathCount=len(state.git_changed_paths),
            paths=cap_changeset_paths(state.git_changed_paths),
        )
        state.prog.phase(
            f"LLM pack: git-diff change-set → {len(state.llm_files)} file(s) "
            f"(base={resolved_base or 'worktree'}; "
            f"{len(state.git_changed_paths)} path(s) from git)"
        )
        if not state.llm_files:
            state.prog.detail(
                "Change-set intersection with inventory is empty — "
                "Slow Brain will skip (scanners/Fast Brain still ran)"
            )


def _apply_triage_routing(state: ReviewRun) -> None:
    state.triage_bypassed = False
    state.triage_plan = None
    if state.cfg.ci.triage_routing:
        avail = [f.relative for f in (state.llm_files or state.files)]
        changed_paths = None
        if state.pack_mode == "changed" and state.diff is not None:
            changed_paths = sorted(set(state.diff.added) | set(state.diff.changed))
        state.triage_plan = triage_llm_plan(
            state.scanner_issues,
            available_files=avail,
            config=state.cfg.ci,
            changed_files=changed_paths,
            heuristic_issues=state.heur_issues,
            include_heuristics=state.cfg.fast_brain.triage_include_heuristics,
        )
        for note in state.triage_plan.notes:
            state.prog.detail(note)
        if state.triage_plan.llm_bypassed:
            state.triage_bypassed = True
            state.prog.phase("LLM bypassed (scanners/heuristics clean at triage floor)")
            state.report = FindingReport(
                confidence=80 if state.scanner_runs else 60,
                summary=Summary(),
                issues=state.non_llm_issues,
                durabilityGaps=list(state.scanner_gaps) + list(state.triage_plan.notes),
                scannerRuns=list(state.scanner_runs),
                supplyChain=state.supply_chain,
                llmSkipped=True,
                llmBypassed=True,
                triageHits=0,
            )
            state.report.summary = state.report.recount_summary()
        elif state.triage_plan.pack_files:
            state.prog.phase(
                f"LLM triage: {state.triage_plan.triage_hits} hit(s) → "
                f"{len(state.triage_plan.pack_files)} file(s)"
            )
            # Prefer Fast Brain inventory so heuristic hits outside the
            # Slow Brain top-N sample can still enter the LLM pack.
            state.llm_files = select_pack_entries(
                state.fast_files, state.triage_plan.pack_files
            )
            if not state.llm_files:
                state.llm_files = select_pack_entries(
                    state.files, state.triage_plan.pack_files
                )
            if state.git_diff_requested and state.git_changed_paths:
                from repolens.changeset import filter_entries_to_changeset

                state.llm_files = filter_entries_to_changeset(
                    state.llm_files, state.git_changed_paths
                )
            state.scanner_gaps.extend(
                n for n in state.triage_plan.notes if n not in state.scanner_gaps
            )


def _reuse_or_skip_llm(state: ReviewRun) -> None:
    prior_bundle = None
    if state.store is not None:
        prior_bundle = load_last_llm_report(state.store)
    if prior_bundle is None:
        prior_bundle = bootstrap_from_out_dir(state.out)
    if prior_bundle is not None:
        prior, saved_at, prior_model = prior_bundle
        state.report = merge_reused_report(
            prior,
            scanner_issues=state.non_llm_issues,
            scanner_runs=list(state.scanner_runs),
            scanner_gaps=list(state.scanner_gaps),
            saved_at=saved_at,
            model=prior_model,
        )
        state.prog.phase(
            f"LLM: reused last successful findings "
            f"({state.report.llmReusedFrom})"
        )
        state.prog.detail(
            "No fingerprint delta — carried forward prior AI issues; "
            "scanners refreshed this run. Use --full to re-run the model."
        )
        if state.store is not None and state.store.get_meta("last_llm_report_json") is None:
            # Persist bootstrap so later skips do not re-scan out/.
            save_last_llm_report(
                state.store,
                prior.model_copy(update={"llmCompleted": True}),
                model=prior_model or None,
                mode=state.mode,
            )
    else:
        if state.git_diff_requested:
            gap = (
                "LLM skipped: --git-diff change-set intersected the "
                "inventory with zero files (empty or unscanned paths), "
                "and no prior successful LLM snapshot is available to reuse. "
                "Commit/stage relevant sources or omit --git-diff."
            )
            state.prog.phase(
                "LLM: skipped — empty git change-set intersection "
                "and no prior LLM snapshot to reuse"
            )
        else:
            gap = (
                "LLM skipped: --changed / adaptive mode=changed found no "
                "added or changed files since the last fingerprint sync, "
                "and no prior successful LLM snapshot is available to reuse. "
                "Run once without --changed (or with --full), then --changed "
                "will carry findings forward. Or use --scanners-only."
            )
            state.prog.phase(
                "LLM: skipped — no fingerprint delta and no prior LLM "
                "snapshot to reuse"
            )
        state.prog.detail(
            "Tip: run a full/auto LLM pass once to seed .repolens/; "
            "or --scanners-only for a fast no-AI check"
        )
        state.report = FindingReport(
            confidence=55,
            summary=Summary(),
            issues=state.non_llm_issues,
            durabilityGaps=[gap] + list(state.scanner_gaps),
            scannerRuns=list(state.scanner_runs),
            llmSkipped=True,
        )
        state.report.summary = state.report.recount_summary()


def _prepare_llm_prompt(state: ReviewRun) -> None:
    if state.store is not None:
        history = state.store.successful_llm_seconds()
        recommended = recommend_timeout(
            history, adaptive=state.cfg.adaptive, file_count=len(state.llm_files)
        )
        state.store.set_meta("recommended_timeout_seconds", f"{recommended:g}")
        if state.timeout_override is None and state.cfg.model.timeout_seconds is None:
            state.cfg.model.timeout_seconds = resolve_effective_timeout(
                explicit=None,
                recommended=recommended,
                provider=state.cfg.model.provider,
                adaptive=state.cfg.adaptive,
            )
        state.prog.detail(
            f"timeout: {resolve_llm_timeout(state.cfg.model):g}s "
            f"(recommended {recommended:g}s)"
        )
        _maybe_sync_fts(state.store, state.root, state.fast_files, state.diff)

    state.use_deep = state.cfg.deep.enabled if state.deep is None else state.deep
    state.llm_pack_file_count = len(state.llm_files)
    local_ctx = ""
    if state.cfg.local_learning.enabled:
        from repolens.learning.consent import has_consent
        from repolens.learning.retrieve import retrieve_context

        if has_consent(state.root):
            query = f"{state.mode} " + " ".join(
                f.relative for f in state.llm_files[:40]
            )
            local_ctx = retrieve_context(state.root, query, limit=5)
            if local_ctx:
                state.prog.detail("attached local-learning context")

    from repolens.scanners.evidence import format_scanner_evidence_for_prompt

    scanner_ctx = format_scanner_evidence_for_prompt(state.scanner_issues)
    if scanner_ctx:
        state.prog.detail(
            f"attached scanner evidence ({len(state.scanner_issues)} finding(s))"
        )
    heur_ctx = ""
    if state.heur_issues:
        lines = [
            "### Fast Brain heuristic hits (context only)",
            *[
                f"- [{i.severity}] {i.file}:{i.line} {i.title}"
                for i in state.heur_issues[:40]
            ],
        ]
        heur_ctx = "\n".join(lines)
    state.prompt_prefix = "\n\n".join(
        part
        for part in (
            scanner_ctx,
            heur_ctx,
            local_ctx,
            _complexity_ai_prefix(state.root, state.complexity_result, state.cfg),
        )
        if part
    )

    state.provider = state.cfg.model.provider or "unknown"
    state.model_name = state.cfg.model.model or default_model(state.cfg.model.provider)
    state.timeout = resolve_llm_timeout(state.cfg.model)
    state.llm_label = (
        f"LLM: {state.model_name} via {state.provider} "
        f"(timeout {state.timeout:g}s — large repos can take several minutes)"
    )
    state.started = time.time()
    state._llm_t0 = time.monotonic()
