"""End-to-end review orchestration."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from repolens.adaptive import (
    recommend_timeout,
    resolve_effective_timeout,
    select_pack_paths,
)
from repolens.config import ModelConfig, RepoLensConfig, load_config, resolve_report_dir
from repolens.inventory import list_files
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
from repolens.schema import FindingReport, Summary


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

    prog.phase("Inventory: scanning files…")
    files = list_files(root, mode=review_mode, since=since)
    prog.phase(f"Inventory: {len(files)} reviewable file(s)")
    if prog.verbose and files:
        sample = ", ".join(f.relative for f in files[:8])
        more = f" (+{len(files) - 8} more)" if len(files) > 8 else ""
        prog.detail(f"sample: {sample}{more}")

    store, diff = _sync_adaptive_cache(root, files, cfg=cfg, prog=prog)

    if out_dir is not None:
        out = out_dir
    else:
        out = resolve_report_dir(root, cfg.general.report_dir)

    try:
        if dry_run:
            prog.phase("Dry-run: writing inventory report (no scanners / LLM)…")
            empty = FindingReport(
                confidence=0,
                summary=Summary(),
                issues=[],
                durabilityGaps=["dry-run: no LLM call"],
                durationSeconds=round(time.time() - run_started, 1),
            )
            md = write_markdown_report(empty, out, mode=mode) if fmt in {"md", "both"} else None
            js = (
                write_json_report(empty, out, mode=mode)
                if fmt in {"json", "both"}
                else None
            )
            prog.phase("Done (dry-run)")
            return ReviewResult(
                report=empty,
                markdown_path=md,
                json_path=js,
                files_scanned=len(files),
                dry_run=True,
            )

        tools = parse_scanners_flag(scanners, config_enabled=cfg.scanners.enabled)
        if scanners_only and tools is None:
            tools = list(cfg.scanners.enabled)

        scanner_runs = []
        scanner_issues = []
        scanner_gaps: list[str] = []
        if tools:
            prog.phase(f"Scanners: running {', '.join(tools)}…")
            scanner_runs, scanner_issues, scanner_gaps = run_scanners(root, tools)
            for run in scanner_runs:
                prog.detail(
                    f"{run.tool}: {run.status}" + (f" — {run.detail}" if run.detail else "")
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

        if scanners_only:
            all_ran = bool(scanner_runs) and all(r.status == "ran" for r in scanner_runs)
            report = FindingReport(
                confidence=75 if all_ran else 55,
                summary=Summary(),
                issues=list(scanner_issues),
                durabilityGaps=list(scanner_gaps)
                or (["scanners-only: no scanners selected"] if not tools else []),
                scannerRuns=list(scanner_runs),
            )
            report.summary = report.recount_summary()
        elif not files:
            report = FindingReport(
                confidence=90,
                summary=Summary(),
                issues=list(scanner_issues),
                durabilityGaps=["No reviewable files found (check ignores / --mode diff)"]
                + scanner_gaps,
                scannerRuns=list(scanner_runs),
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

            if not llm_files:
                prior_bundle = None
                if store is not None:
                    prior_bundle = load_last_llm_report(store)
                if prior_bundle is None:
                    prior_bundle = bootstrap_from_out_dir(out)
                if prior_bundle is not None:
                    prior, saved_at, prior_model = prior_bundle
                    report = merge_reused_report(
                        prior,
                        scanner_issues=list(scanner_issues),
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
                        issues=list(scanner_issues),
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
                    _maybe_sync_fts(store, root, files, diff)

                use_deep = cfg.deep.enabled if deep is None else deep
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

                provider = cfg.model.provider or "unknown"
                model_name = cfg.model.model or default_model(cfg.model.provider)
                timeout = resolve_llm_timeout(cfg.model)
                llm_label = (
                    f"LLM: {model_name} via {provider} "
                    f"(timeout {timeout:g}s — large repos can take several minutes)"
                )
                started = time.time()
                try:
                    if use_deep:
                        # Per-pass waiting lives inside _analyze_deep_passes.
                        report = _analyze_deep_passes(
                            root=root,
                            mode=mode,
                            full_audit=full_audit,
                            files=files,
                            llm_files=llm_files,
                            cfg=cfg,
                            prog=prog,
                            prompt_prefix=local_ctx,
                            scanner_runs=scanner_runs,
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
                                mode, root, llm_files, full_audit=full_audit
                            )
                            if local_ctx:
                                prompt = local_ctx + "\n\n" + prompt
                            prog.detail(f"prompt size ≈ {len(prompt):,} characters")
                            report = _analyze_with_repair(
                                prompt,
                                cfg.model,
                                progress=prog,
                                root=root,
                                on_delta=gen.note_delta,
                            )
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

                if scanner_issues or scanner_runs or scanner_gaps:
                    report.issues = list(report.issues) + list(scanner_issues)
                    report.scannerRuns = list(scanner_runs)
                    report.durabilityGaps = list(report.durabilityGaps) + list(
                        scanner_gaps
                    )
                    report.summary = report.recount_summary()

                report.llmCompleted = True
                report.llmSkipped = False
                report.llmReusedFrom = None
                if store is not None:
                    save_last_llm_report(
                        store,
                        report,
                        model=model_name,
                        mode=mode,
                    )

        report.durationSeconds = round(time.time() - run_started, 1)
        prog.phase(f"Writing report → {out}")
        md = write_markdown_report(report, out, mode=mode) if fmt in {"md", "both"} else None
        js = (
            write_json_report(report, out, mode=mode)
            if fmt in {"json", "both"}
            else None
        )
        prog.phase("Done")
        return ReviewResult(
            report=report,
            markdown_path=md,
            json_path=js,
            files_scanned=len(files),
            dry_run=False,
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


def fail_on_triggered(report: FindingReport, fail_on: str | None) -> bool:
    if not fail_on:
        return False
    order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    key = fail_on.upper()
    if key not in order:
        raise ValueError(
            f"Invalid --fail-on severity {fail_on!r}; use CRITICAL|HIGH|MEDIUM|LOW"
        )
    threshold = order[key]
    for issue in report.issues:
        if order[issue.severity.value] >= threshold:
            return True
    return False

