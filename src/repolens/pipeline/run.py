"""End-to-end review orchestration."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC
from pathlib import Path

from repolens.adaptive import (
    recommend_timeout,
    resolve_effective_timeout,
    select_pack_paths,
)
from repolens.config import ModelConfig, RepoLensConfig, load_config, resolve_report_dir
from repolens.last_llm import (
    bootstrap_from_out_dir,
    load_last_llm_report,
    merge_reused_report,
    save_last_llm_report,
)
from repolens.llm import default_model, resolve_llm_timeout
from repolens.pipeline.deep_exec import (
    _analyze_deep_passes,
    _maybe_sync_fts,
    _sync_adaptive_cache,
)
from repolens.pipeline.prompt import build_prompt
from repolens.pipeline.types import ReviewResult, ScannerRequirementError
from repolens.progress import LlmGenerateProgress, ReviewProgress, null_progress
from repolens.report import write_json_report, write_markdown_report
from repolens.scanners.runner import missing_required, parse_scanners_flag, run_scanners
from repolens.scanners.sca import build_supply_chain, dedupe_sca_issues
from repolens.schema import FindingReport, ProvenanceBlock, Summary, SupplyChainBlock
from repolens.triage import (
    fail_on_triggered as _fail_on_triggered,
)
from repolens.triage import (
    select_pack_entries,
    stamp_issue_sources,
    triage_llm_plan,
)


def fail_on_triggered(
    report: FindingReport,
    fail_on: str | None,
    *,
    scanner_only: bool = False,
) -> bool:
    """Re-export with Phase 6.3 scanner-only gate support."""
    return _fail_on_triggered(report, fail_on, scanner_only=scanner_only)


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
) -> ReviewResult:
    if force_full and force_changed:
        raise ValueError("--full and --changed cannot be combined")
    prog = progress or null_progress()
    root = path.resolve()
    run_started = time.time()
    cfg = config or load_config(root, trust_project=trust_project)
    if model_override:
        cfg.model.model = model_override
    if timeout_override is not None:
        if timeout_override <= 0:
            raise ValueError("--timeout must be a positive number of seconds")
        cfg.model.timeout_seconds = timeout_override
    if verify_findings is True:
        cfg.deep.verify_findings = True
    elif verify_findings is False:
        cfg.deep.verify_findings = False
    from repolens.heuristics import run_heuristics
    from repolens.inventory import scan_inventory
    from repolens.packs.registry import resolve_enabled_packs

    pack_ids = resolve_enabled_packs([*cfg.packs.enabled, *(packs or [])])
    cfg.packs.enabled = list(pack_ids)

    # Phase 6.3: --ci enables triage routing + changed pack + single-shot LLM
    if ci:
        cfg.ci.triage_routing = True
        if not force_full and not force_changed:
            force_changed = True
        if deep is None and cfg.ci.max_llm_passes_in_ci <= 1:
            deep = False
        prog.detail(
            "CI mode: triage routing on "
            "(LLM bypass when scanners/heuristics clean; snippet pack on hits)"
        )

    # Sentinel prefers scanners evidence; keep enabled list (opt-out via --scanners off)
    if mode == "sentinel" and scanners is None:
        scanners = "auto"

    prog.phase("Inventory: scanning files…")
    fast_max = cfg.fast_brain.max_files
    fast_inv = scan_inventory(
        root, mode=review_mode, since=since, max_files=fast_max
    )
    fast_files = fast_inv.files
    llm_cap = cfg.general.max_files
    if llm_cap <= 0:
        files = list(fast_files)
    else:
        files = list(fast_files[:llm_cap])

    if fast_inv.truncated:
        prog.phase(
            f"Fast brain inventory: {len(fast_files)} of {fast_inv.total_matched} "
            f"matched (cap max_files={fast_inv.max_files})"
        )
    else:
        prog.phase(f"Fast brain inventory: {len(fast_files)} matched file(s)")
    if len(files) < len(fast_files):
        prog.detail(
            f"Slow brain LLM pool: top {len(files)} by priority "
            f"(general.max_files={llm_cap}); Fast Brain heuristics use all "
            f"{len(fast_files)}"
        )
        inventory_notes = [
            (
                f"Two-Lane: Fast Brain sees {len(fast_files)} file(s); "
                f"LLM sample pool is {len(files)} "
                f"(general.max_files={llm_cap}). "
                "Deterministic scanners still cover the full tree."
            )
        ]
    else:
        inventory_notes = []
        note = fast_inv.truncation_note()
        if note:
            inventory_notes.append(note)
    if prog.verbose and fast_files:
        sample = ", ".join(f.relative for f in fast_files[:8])
        more = f" (+{len(fast_files) - 8} more)" if len(fast_files) > 8 else ""
        prog.detail(f"sample: {sample}{more}")

    # Fingerprints track Fast Brain set (not LLM slice alone).
    store, diff = _sync_adaptive_cache(root, fast_files, cfg=cfg, prog=prog)

    fast_brain_file_count = len(fast_files)
    llm_pack_file_count = 0
    fast_brain_seconds: float | None = None
    llm_seconds_prov: float | None = None
    heur_result = None

    if out_dir is not None:
        out = out_dir
    else:
        out = resolve_report_dir(root, cfg.general.report_dir)

    try:
        if dry_run:
            from datetime import datetime

            from repolens import __version__

            prog.phase("Dry-run: writing inventory report (no scanners / LLM)…")
            empty = FindingReport(
                confidence=0,
                summary=Summary(),
                issues=[],
                durabilityGaps=["dry-run: no LLM call"] + list(inventory_notes),
                durationSeconds=round(time.time() - run_started, 1),
                provenance=ProvenanceBlock(
                    repoLensVersion=__version__,
                    gitSha=_git_sha(root),
                    fastBrainFiles=fast_brain_file_count,
                    llmPackFiles=0,
                ),
            )
            report_when = datetime.now(UTC)
            md = (
                write_markdown_report(empty, out, mode=mode, when=report_when)
                if fmt in {"md", "both"}
                else None
            )
            js = (
                write_json_report(empty, out, mode=mode, when=report_when)
                if fmt in {"json", "both"}
                else None
            )
            prog.phase("Done (dry-run)")
            return ReviewResult(
                report=empty,
                markdown_path=md,
                json_path=js,
                files_scanned=fast_brain_file_count,
                dry_run=True,
            )

        tools = parse_scanners_flag(scanners, config_enabled=cfg.scanners.enabled)
        if scanners_only and tools is None:
            tools = list(cfg.scanners.enabled)

        scanner_runs = []
        scanner_issues = []
        scanner_gaps: list[str] = []
        supply_chain: SupplyChainBlock | None = None
        triage_plan = None
        if tools:
            prog.phase(f"Scanners: running {', '.join(tools)}…")
            scanner_runs, scanner_issues, scanner_gaps = run_scanners(root, tools)
            for run in scanner_runs:
                prog.detail(
                    f"{run.tool}: {run.status}" + (f" — {run.detail}" if run.detail else "")
                )
            before_dedupe = len(scanner_issues)
            scanner_issues = dedupe_sca_issues(scanner_issues)
            if len(scanner_issues) < before_dedupe:
                prog.detail(
                    f"SCA: deduped {before_dedupe - len(scanner_issues)} "
                    "duplicate OSV/Trivy advisory row(s)"
                )
            if cfg.deep.usage_hints:
                from repolens.scanners.usage_hints import apply_usage_hints

                scanner_issues = apply_usage_hints(root, scanner_issues)
                hinted = sum(1 for i in scanner_issues if i.usageHint)
                if hinted:
                    prog.detail(
                        f"SCA usage hints: {hinted} package finding(s) "
                        "(not reachability)"
                    )
            prog.phase(
                f"Scanners: finished ({len(scanner_issues)} finding(s), "
                f"{sum(1 for r in scanner_runs if r.status == 'ran')}/{len(scanner_runs)} ran)"
            )
            require = require_scanners or cfg.scanners.require
            if require:
                missing = missing_required(tools, scanner_runs)
                if missing:
                    raise ScannerRequirementError(missing)
        else:
            prog.detail("Scanners: skipped (off / none selected)")

        want_supply = cfg.scanners.sbom or cfg.scanners.licenses
        trivy_requested = bool(tools) and "trivy" in tools
        if want_supply:
            from repolens.scanners.base import resolve_binary

            trivy_available = resolve_binary("trivy") is not None
            if trivy_available or trivy_requested:
                prog.phase("Supply chain: SBOM / licenses…")
                supply_chain, sc_gaps = build_supply_chain(
                    root,
                    out,
                    sbom=cfg.scanners.sbom,
                    licenses=cfg.scanners.licenses,
                )
                scanner_gaps.extend(sc_gaps)
                if supply_chain and supply_chain.sbomPath:
                    prog.detail(f"SBOM: {supply_chain.sbomPath}")
                elif sc_gaps:
                    prog.detail(sc_gaps[0])
            else:
                prog.detail(
                    "Supply chain: skipped (install Trivy for SBOM/licenses — "
                    "`repolens plugins install trivy`)"
                )

        prog.phase(
            f"Fast brain: heuristics on {len(fast_files)} file(s) "
            f"(workers={cfg.fast_brain.parallel_workers})…"
        )
        _fb_t0 = time.monotonic()
        heur_result = run_heuristics(
            root,
            fast_files,
            mega_file_lines=cfg.deep.mega_file_lines,
            mega_file_exclude_globs=cfg.deep.mega_file_exclude_globs or None,
            pack_ids=pack_ids or None,
            workers=cfg.fast_brain.parallel_workers,
        )
        fast_brain_seconds = round(time.monotonic() - _fb_t0, 1)
        heur_issues = list(heur_result.issues)
        prog.detail(
            f"Fast brain: {len(heur_issues)} heuristic finding(s), "
            f"{len(heur_result.hot_paths)} hot path(s)"
        )
        if pack_ids:
            prog.detail(f"Domain packs enabled: {', '.join(pack_ids)}")

        if scanners_only:
            all_ran = bool(scanner_runs) and all(r.status == "ran" for r in scanner_runs)
            report = FindingReport(
                confidence=75 if all_ran else 55,
                summary=Summary(),
                issues=list(scanner_issues) + heur_issues,
                durabilityGaps=list(scanner_gaps)
                or (["scanners-only: no scanners selected"] if not tools else []),
                scannerRuns=list(scanner_runs),
                supplyChain=supply_chain,
            )
            report.summary = report.recount_summary()
        elif not files and not fast_files:
            report = FindingReport(
                confidence=90,
                summary=Summary(),
                issues=list(scanner_issues) + heur_issues,
                durabilityGaps=["No reviewable files found (check ignores / --mode diff)"]
                + scanner_gaps,
                scannerRuns=list(scanner_runs),
                supplyChain=supply_chain,
            )
            report.summary = report.recount_summary()
        else:
            if force_changed:
                pack_mode = "changed"
            elif force_full:
                pack_mode = "full"
            else:
                pack_mode = cfg.adaptive.mode
            llm_files = files
            if store is not None and diff is not None and cfg.adaptive.enabled:
                llm_files = select_pack_paths(files, diff, mode=pack_mode)
                delta_n = len(diff.added) + len(diff.changed)
                note = ""
                if (
                    pack_mode == "auto"
                    and delta_n == 0
                    and len(llm_files) == len(files)
                    and files
                ):
                    note = (
                        " — no fingerprint delta → full pack "
                        "(use --changed for delta-only smoke)"
                    )
                prog.phase(
                    f"LLM pack: {len(llm_files)}/{len(files)} file(s) "
                    f"(adaptive mode={pack_mode}){note}"
                )

            triage_bypassed = False
            triage_plan = None
            if cfg.ci.triage_routing:
                avail = [f.relative for f in (llm_files or files)]
                changed_paths = None
                if pack_mode == "changed" and diff is not None:
                    changed_paths = sorted(set(diff.added) | set(diff.changed))
                triage_plan = triage_llm_plan(
                    scanner_issues,
                    available_files=avail,
                    config=cfg.ci,
                    changed_files=changed_paths,
                    heuristic_issues=heur_issues,
                    include_heuristics=cfg.fast_brain.triage_include_heuristics,
                )
                for note in triage_plan.notes:
                    prog.detail(note)
                if triage_plan.llm_bypassed:
                    triage_bypassed = True
                    prog.phase("LLM bypassed (scanners/heuristics clean at triage floor)")
                    report = FindingReport(
                        confidence=80 if scanner_runs else 60,
                        summary=Summary(),
                        issues=list(scanner_issues) + heur_issues,
                        durabilityGaps=list(scanner_gaps) + list(triage_plan.notes),
                        scannerRuns=list(scanner_runs),
                        supplyChain=supply_chain,
                        llmSkipped=True,
                        llmBypassed=True,
                        triageHits=0,
                    )
                    report.summary = report.recount_summary()
                elif triage_plan.pack_files:
                    prog.phase(
                        f"LLM triage: {triage_plan.triage_hits} hit(s) → "
                        f"{len(triage_plan.pack_files)} file(s)"
                    )
                    # Prefer Fast Brain inventory so heuristic hits outside the
                    # Slow Brain top-N sample can still enter the LLM pack.
                    llm_files = select_pack_entries(
                        fast_files, triage_plan.pack_files
                    )
                    if not llm_files:
                        llm_files = select_pack_entries(
                            files, triage_plan.pack_files
                        )
                    scanner_gaps.extend(
                        n for n in triage_plan.notes if n not in scanner_gaps
                    )

            if triage_bypassed:
                pass
            elif not llm_files:
                prior_bundle = None
                if store is not None:
                    prior_bundle = load_last_llm_report(store)
                if prior_bundle is None:
                    prior_bundle = bootstrap_from_out_dir(out)
                if prior_bundle is not None:
                    prior, saved_at, prior_model = prior_bundle
                    report = merge_reused_report(
                        prior,
                        scanner_issues=list(scanner_issues) + heur_issues,
                        scanner_runs=list(scanner_runs),
                        scanner_gaps=list(scanner_gaps),
                        saved_at=saved_at,
                        model=prior_model,
                    )
                    prog.phase(
                        f"LLM: reused last successful findings "
                        f"({report.llmReusedFrom})"
                    )
                    prog.detail(
                        "No fingerprint delta — carried forward prior AI issues; "
                        "scanners refreshed this run. Use --full to re-run the model."
                    )
                    if store is not None and store.get_meta("last_llm_report_json") is None:
                        # Persist bootstrap so later skips do not re-scan out/.
                        save_last_llm_report(
                            store,
                            prior.model_copy(update={"llmCompleted": True}),
                            model=prior_model or None,
                            mode=mode,
                        )
                else:
                    gap = (
                        "LLM skipped: --changed / adaptive mode=changed found no "
                        "added or changed files since the last fingerprint sync, "
                        "and no prior successful LLM snapshot is available to reuse. "
                        "Run once without --changed (or with --full), then --changed "
                        "will carry findings forward. Or use --scanners-only."
                    )
                    prog.phase(
                        "LLM: skipped — no fingerprint delta and no prior LLM "
                        "snapshot to reuse"
                    )
                    prog.detail(
                        "Tip: run a full/auto LLM pass once to seed .repolens/; "
                        "or --scanners-only for a fast no-AI check"
                    )
                    report = FindingReport(
                        confidence=55,
                        summary=Summary(),
                        issues=list(scanner_issues) + heur_issues,
                        durabilityGaps=[gap] + list(scanner_gaps),
                        scannerRuns=list(scanner_runs),
                        llmSkipped=True,
                    )
                    report.summary = report.recount_summary()
            else:
                if store is not None:
                    history = store.successful_llm_seconds()
                    recommended = recommend_timeout(
                        history, adaptive=cfg.adaptive, file_count=len(llm_files)
                    )
                    store.set_meta("recommended_timeout_seconds", f"{recommended:g}")
                    if timeout_override is None and cfg.model.timeout_seconds is None:
                        cfg.model.timeout_seconds = resolve_effective_timeout(
                            explicit=None,
                            recommended=recommended,
                            provider=cfg.model.provider,
                            adaptive=cfg.adaptive,
                        )
                    prog.detail(
                        f"timeout: {resolve_llm_timeout(cfg.model):g}s "
                        f"(recommended {recommended:g}s)"
                    )
                    _maybe_sync_fts(store, root, fast_files, diff)

                use_deep = cfg.deep.enabled if deep is None else deep
                llm_pack_file_count = len(llm_files)
                local_ctx = ""
                if cfg.local_learning.enabled:
                    from repolens.learning.consent import has_consent
                    from repolens.learning.retrieve import retrieve_context

                    if has_consent(root):
                        query = f"{mode} " + " ".join(
                            f.relative for f in llm_files[:40]
                        )
                        local_ctx = retrieve_context(root, query, limit=5)
                        if local_ctx:
                            prog.detail("attached local-learning context")

                from repolens.scanners.evidence import format_scanner_evidence_for_prompt

                scanner_ctx = format_scanner_evidence_for_prompt(scanner_issues)
                if scanner_ctx:
                    prog.detail(
                        f"attached scanner evidence ({len(scanner_issues)} finding(s))"
                    )
                heur_ctx = ""
                if heur_issues:
                    lines = [
                        "### Fast Brain heuristic hits (context only)",
                        *[
                            f"- [{i.severity}] {i.file}:{i.line} {i.title}"
                            for i in heur_issues[:40]
                        ],
                    ]
                    heur_ctx = "\n".join(lines)
                prompt_prefix = "\n\n".join(
                    part for part in (scanner_ctx, heur_ctx, local_ctx) if part
                )

                provider = cfg.model.provider or "unknown"
                model_name = cfg.model.model or default_model(cfg.model.provider)
                timeout = resolve_llm_timeout(cfg.model)
                llm_label = (
                    f"LLM: {model_name} via {provider} "
                    f"(timeout {timeout:g}s — large repos can take several minutes)"
                )
                started = time.time()
                _llm_t0 = time.monotonic()
                try:
                    if use_deep:
                        # Per-pass waiting lives inside _analyze_deep_passes.
                        report = _analyze_deep_passes(
                            root=root,
                            mode=mode,
                            full_audit=full_audit,
                            files=fast_files,
                            llm_files=llm_files,
                            cfg=cfg,
                            prog=prog,
                            prompt_prefix=prompt_prefix,
                            scanner_runs=scanner_runs,
                            heur_result=heur_result,
                        )
                    else:
                        gen = LlmGenerateProgress()
                        ollama_base = (
                            cfg.model.base_url if provider == "ollama" else None
                        )

                        def status_fn(
                            progress: LlmGenerateProgress = gen,
                            base: str | None = ollama_base,
                            use_ollama: bool = provider == "ollama",
                        ) -> str | None:
                            bits = [progress.summary()]
                            if use_ollama:
                                from repolens.provider_status import (
                                    ollama_running_summary,
                                )

                                live = ollama_running_summary(base)
                                if live:
                                    bits.append(live)
                            return " | ".join(bits)

                        with prog.waiting(
                            llm_label,
                            hint="streaming chat completions",
                            status_fn=status_fn,
                        ):
                            prog.phase("Building LLM prompt…")
                            prompt = build_prompt(
                                mode,
                                root,
                                llm_files,
                                full_audit=full_audit,
                                pack_ids=pack_ids,
                            )
                            if prompt_prefix:
                                prompt = prompt_prefix + "\n\n" + prompt
                            prog.detail(f"prompt size ≈ {len(prompt):,} characters")
                            report = _analyze_with_repair(
                                prompt,
                                cfg.model,
                                progress=prog,
                                root=root,
                                on_delta=gen.note_delta,
                            )
                            from repolens.consistency import apply_llm_consistency
                            from repolens.fp_calibrations import apply_fp_calibrations

                            report.issues = apply_fp_calibrations(
                                report.issues, cfg.deep
                            )
                            if (cfg.deep.critical_consistency or "").lower() == "llm":
                                prog.phase("Critical consistency (LLM confirm)…")
                                report.issues = apply_llm_consistency(
                                    report.issues, cfg.deep, cfg.model
                                )
                            report.summary = report.recount_summary()
                        gen.mark_done()
                except BaseException:
                    if store is not None:
                        store.record_run(
                            started_at=started,
                            finished_at=time.time(),
                            mode=mode,
                            provider=cfg.model.provider,
                            model=model_name,
                            files_in_prompt=len(llm_files),
                            llm_seconds=None,
                            timeout_used=timeout,
                            outcome="error",
                        )
                    raise
                else:
                    llm_seconds = time.time() - started
                    llm_seconds_prov = round(time.monotonic() - _llm_t0, 1)
                    if store is not None:
                        store.record_run(
                            started_at=started,
                            finished_at=time.time(),
                            mode=mode,
                            provider=cfg.model.provider,
                            model=model_name,
                            files_in_prompt=len(llm_files),
                            llm_seconds=llm_seconds,
                            timeout_used=timeout,
                            outcome="ok",
                        )
                        hist = store.successful_llm_seconds()
                        rec = recommend_timeout(
                            hist, adaptive=cfg.adaptive, file_count=len(llm_files)
                        )
                        store.set_meta("recommended_timeout_seconds", f"{rec:g}")

                extra_issues = list(scanner_issues)
                if not use_deep:
                    # Deep path already merged Fast Brain heuristics.
                    extra_issues.extend(heur_issues)
                if extra_issues or scanner_runs or scanner_gaps:
                    report.issues = list(report.issues) + extra_issues
                    report.scannerRuns = list(scanner_runs)
                    report.durabilityGaps = list(report.durabilityGaps) + list(
                        scanner_gaps
                    )
                    report.summary = report.recount_summary()

                report.issues = stamp_issue_sources(report.issues, default_llm=True)
                report.llmCompleted = True
                report.llmSkipped = False
                report.llmReusedFrom = None
                if triage_plan is not None:
                    report.triageHits = triage_plan.triage_hits
                    report.llmBypassed = False
                if store is not None:
                    save_last_llm_report(
                        store,
                        report,
                        model=model_name,
                        mode=mode,
                    )

        report.durationSeconds = round(time.time() - run_started, 1)
        if supply_chain is not None:
            report.supplyChain = supply_chain
        if inventory_notes:
            report.durabilityGaps = list(report.durabilityGaps) + [
                n for n in inventory_notes if n not in report.durabilityGaps
            ]
        from repolens import __version__
        from repolens.issue_ids import stamp_issue_ids

        report.issues = stamp_issue_ids(stamp_issue_sources(report.issues))
        from repolens.cluster import cluster_near_duplicates
        from repolens.feedback_store import apply_feedback_calibrations
        from repolens.suppressions import apply_suppressions

        report.issues = apply_feedback_calibrations(report.issues, root, cfg.deep)
        if cfg.deep.cluster_duplicates:
            before_cluster = len(report.issues)
            report.issues = cluster_near_duplicates(report.issues)
            if len(report.issues) < before_cluster:
                prog.detail(
                    f"Clustered {before_cluster - len(report.issues)} "
                    "near-duplicate finding(s)"
                )
        active, suppressed = apply_suppressions(root, report.issues)
        report.issues = active
        report.suppressedIssues = suppressed
        if suppressed:
            prog.detail(
                f"Suppressions: {len(suppressed)} finding(s) "
                f"(ignore file / disable comments)"
            )
        report.summary = report.recount_summary()
        report.provenance = ProvenanceBlock(
            repoLensVersion=__version__,
            gitSha=_git_sha(root),
            model=cfg.model.model,
            provider=cfg.model.provider,
            scannerTools=[r.tool for r in report.scannerRuns],
            triageRouting=cfg.ci.triage_routing,
            llmBypassed=bool(report.llmBypassed),
            triageHits=int(report.triageHits or 0),
            failOnScannerOnly=bool(
                cfg.ci.triage_routing and cfg.ci.fail_on_scanner_only
            ),
            fastBrainFiles=fast_brain_file_count,
            llmPackFiles=llm_pack_file_count,
            fastBrainSeconds=fast_brain_seconds,
            llmSeconds=llm_seconds_prov,
            notes=list(triage_plan.notes) if triage_plan is not None else [],
        )
        # Phase 6.4: stamp locationVerified before Markdown/SARIF write
        from repolens.sarif import verify_issue_location, write_sarif_report

        for issue in report.issues:
            verify_issue_location(root, issue)
        from repolens.consistency import apply_heuristic_consistency

        if (cfg.deep.critical_consistency or "").lower() in {"heuristic", "llm"}:
            report.issues = apply_heuristic_consistency(report.issues, cfg.deep)
            report.summary = report.recount_summary()
        from repolens.verify_findings import apply_verify_findings

        if cfg.deep.verify_findings:
            prog.detail("Verify findings: re-checking Critical locations (non-fatal)…")
            report.issues = apply_verify_findings(root, report.issues, cfg.deep)
            report.summary = report.recount_summary()

        from datetime import datetime

        report_when = datetime.now(UTC)
        prog.phase(f"Writing report → {out}")
        md = (
            write_markdown_report(report, out, mode=mode, when=report_when)
            if fmt in {"md", "both"}
            else None
        )
        js = (
            write_json_report(report, out, mode=mode, when=report_when)
            if fmt in {"json", "both"}
            else None
        )
        if js is not None:
            from repolens.explain import write_last_report_pointer

            write_last_report_pointer(root, js)
        elif md is not None and fmt == "md":
            # Prefer JSON for explain; when md-only, still write JSON sidecar for lookup.
            js = write_json_report(report, out, mode=mode, when=report_when)
            from repolens.explain import write_last_report_pointer

            write_last_report_pointer(root, js)
        sarif_path = None
        if sarif:
            sarif_path = write_sarif_report(
                report, root, out_dir=out, mode=mode, when=report_when
            )
            if sarif_path is not None:
                n = sum(1 for i in report.issues if i.locationVerified)
                prog.detail(
                    f"SARIF: {sarif_path.name} "
                    f"({n}/{len(report.issues)} location-verified result(s))"
                )
        prog.phase("Done")
        return ReviewResult(
            report=report,
            markdown_path=md,
            json_path=js,
            files_scanned=fast_brain_file_count,
            dry_run=False,
            sarif_path=sarif_path,
        )
    finally:
        if store is not None:
            store.close()


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
        )
    return result.report



