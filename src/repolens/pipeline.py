"""End-to-end review pipeline."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from repolens.adaptive import (
    recommend_timeout,
    resolve_effective_timeout,
    select_pack_paths,
    sync_project_fingerprints,
)
from repolens.bands import coerce_issue_bands
from repolens.config import ModelConfig, RepoLensConfig, load_config, resolve_report_dir
from repolens.coverage import (
    CoverageResult,
    evaluate_coverage,
    is_lazy_na_reason,
    parse_coverage_notes,
)
from repolens.deep import build_deep_prompt, merge_reports, plan_deep_passes
from repolens.heuristics import run_heuristics
from repolens.inventory import FileEntry, list_files, read_excerpt
from repolens.last_llm import (
    bootstrap_from_out_dir,
    load_last_llm_report,
    merge_reused_report,
    save_last_llm_report,
)
from repolens.llm import default_model, resolve_llm_timeout
from repolens.metrics import compute_audit_metrics
from repolens.playbooks import playbooks_for_mode
from repolens.progress import LlmGenerateProgress, ReviewProgress, null_progress
from repolens.prose import BRITISH_ENGLISH_INSTRUCTION
from repolens.report import write_json_report, write_markdown_report
from repolens.rules.registry import Rule, load_enabled_rules
from repolens.scanners.runner import missing_required, parse_scanners_flag, run_scanners
from repolens.schema import CoverageBlock, FindingReport, ScannerRun, Summary


class ScannerRequirementError(Exception):
    """Raised when --require-scanners is set and a requested tool is missing."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        tools = ", ".join(missing)
        super().__init__(f"Required scanner(s) missing: {tools}. See docs/scanners.md")


@dataclass
class ReviewResult:
    report: FindingReport
    markdown_path: Path | None
    json_path: Path | None
    files_scanned: int
    dry_run: bool


def build_prompt(mode: str, root: Path, files: list[FileEntry], *, full_audit: bool) -> str:
    sections: list[str] = [
        f"Repository root: {root}",
        f"Mode: {mode}",
        f"Files provided: {len(files)}",
        "",
    ]
    for label, content in playbooks_for_mode(mode, full_audit=full_audit):
        sections.append(f"## Playbook: {label}")
        sections.append(content)
        sections.append("")

    sections.append("## Source files")
    for entry in files:
        sections.append(f"### {entry.relative} (priority band {entry.priority_band})")
        sections.append("```")
        sections.append(read_excerpt(entry))
        sections.append("```")
        sections.append("")
    sections.append(BRITISH_ENGLISH_INSTRUCTION)
    sections.append(
        "Analyse the files using the playbooks. Return FindingReport JSON only."
    )
    return "\n".join(sections)


def _sync_adaptive_cache(
    root: Path,
    files: list[FileEntry],
    *,
    cfg: RepoLensConfig,
    prog: ReviewProgress,
):
    """Open store, sync fingerprints, return (store, diff) or (None, None)."""
    if not cfg.adaptive.enabled:
        return None, None
    from repolens.learning.store import ProjectStore

    try:
        store = ProjectStore(root)
        store.open()
        diff = sync_project_fingerprints(store, files)
        prog.phase(
            f"Cache: +{len(diff.added)} added, ~{len(diff.changed)} changed, "
            f"-{len(diff.deleted)} deleted"
        )
        if prog.verbose and (diff.added or diff.changed or diff.deleted):
            if diff.added:
                prog.detail("added: " + ", ".join(diff.added[:8]))
            if diff.changed:
                prog.detail("changed: " + ", ".join(diff.changed[:8]))
            if diff.deleted:
                prog.detail("deleted: " + ", ".join(diff.deleted[:8]))
        return store, diff
    except OSError as exc:
        prog.phase(f"Cache: skipped ({exc})")
        return None, None


def _maybe_sync_fts(store, root: Path, files: list[FileEntry], diff) -> None:
    from repolens.learning.consent import has_consent

    if store is None or diff is None or not has_consent(root):
        return
    for path in diff.deleted:
        store.delete_chunk(path)
    touch = set(diff.added) | set(diff.changed)
    for entry in files:
        if entry.relative not in touch:
            continue
        try:
            text = entry.path.read_text(encoding="utf-8", errors="replace")[:80_000]
        except OSError:
            continue
        store.upsert_chunk(entry.relative, text)


def is_vacuous_llm_report(report: FindingReport) -> bool:
    """True when the model returned a schema-valid but empty/useless report."""
    return (
        report.confidence == 0
        and not report.issues
        and not report.durabilityGaps
    )


def _append_source_files(prompt: str, files: list[FileEntry]) -> str:
    sections = [prompt.rstrip(), "", "## Source files"]
    for entry in files:
        sections.append(f"### {entry.relative} (priority band {entry.priority_band})")
        sections.append("```")
        sections.append(read_excerpt(entry))
        sections.append("```")
        sections.append("")
    return "\n".join(sections)


def _apply_coverage_metrics(
    report: FindingReport,
    coverage: CoverageResult,
    *,
    pass_confidences: dict[str, int],
    scanner_runs: list[ScannerRun] | None = None,
) -> FindingReport:
    """Set gate + band audit confidences; rewrite lazy N/A gaps to missed."""
    runs: list[ScannerRun] = list(scanner_runs or report.scannerRuns)
    metrics = compute_audit_metrics(
        pass_confidences=pass_confidences,
        coverage=coverage,
        scanner_runs=runs,
        issues=report.issues,
    )
    report.confidence = metrics.gate_confidence
    report.securityAuditConfidence = metrics.security_audit_confidence
    report.architectureAuditConfidence = metrics.architecture_audit_confidence
    report.reliabilityAuditConfidence = metrics.reliability_audit_confidence
    report.summary = report.recount_summary()

    cleaned: list[str] = []
    for gap in report.durabilityGaps:
        notes = parse_coverage_notes([gap])
        if notes:
            cid, reason = next(iter(notes.items()))
            if is_lazy_na_reason(reason):
                missed_gap = f"coverage:{cid}: missed — lazy N/A rejected ({reason})"
                if missed_gap not in cleaned:
                    cleaned.append(missed_gap)
                continue
        cleaned.append(gap)
    for mid in coverage.missed:
        marker = f"coverage:{mid}: missed"
        if not any(marker in g for g in cleaned):
            cleaned.append(f"coverage:{mid}: missed — neither issue nor N/A")
    report.durabilityGaps = cleaned
    return report


def _analyze_deep_passes(
    *,
    root: Path,
    mode: str,
    full_audit: bool,
    files: list[FileEntry],
    llm_files: list[FileEntry],
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    prompt_prefix: str = "",
    scanner_runs: list | None = None,
) -> FindingReport:
    """Heuristics → plan passes → structured LLM per pass → merge + coverage."""
    from repolens.llm_structured import analyze_structured

    prog.phase("→ Deep: heuristics…")
    heur = run_heuristics(
        root,
        files,
        mega_file_lines=cfg.deep.mega_file_lines,
        mega_file_exclude_globs=cfg.deep.mega_file_exclude_globs or None,
    )
    if prog.verbose:
        prog.detail(
            f"heuristics: {len(heur.issues)} issue(s), "
            f"{len(heur.hot_paths)} hot path(s)"
        )

    rules: list[Rule] = load_enabled_rules(project_root=root)
    passes = plan_deep_passes(
        mode,
        full_audit=full_audit,
        entries=files,
        hot_paths=heur.hot_paths,
        adaptive_paths=[e.relative for e in llm_files],
        chars_per_pass=cfg.deep.chars_per_pass,
        rules=rules,
    )

    parts: list[FindingReport] = []
    all_coverage_ids: list[str] = []
    raw_dir = root / ".repolens"
    n = len(passes)
    provider = cfg.model.provider or "unknown"
    model_name = cfg.model.model or default_model(cfg.model.provider)
    timeout = resolve_llm_timeout(cfg.model)
    for idx, deep_pass in enumerate(passes, start=1):
        prog.phase(f"→ Deep pass {idx}/{n} ({deep_pass.name})…")
        prompt = build_deep_prompt(deep_pass, rules, deep_pass.coverage_ids)
        prompt = _append_source_files(prompt, deep_pass.files)
        if prompt_prefix:
            prompt = prompt_prefix + "\n\n" + prompt
        wait_label = (
            f"Deep pass {idx}/{n} ({deep_pass.name}) — {model_name} via {provider} "
            f"(timeout {timeout:g}s — large repos can take several minutes)"
        )
        wait_hint = (
            f"streaming chat completions; "
            f"prompt ≈ {len(prompt):,} chars; "
            f"{len(deep_pass.files)} file(s); "
            f"{len(deep_pass.coverage_ids)} coverage id(s)"
        )
        gen = LlmGenerateProgress()
        ollama_base = cfg.model.base_url if provider == "ollama" else None

        def status_fn(
            progress: LlmGenerateProgress = gen,
            base: str | None = ollama_base,
            use_ollama: bool = provider == "ollama",
        ) -> str | None:
            bits = [progress.summary()]
            if use_ollama:
                from repolens.provider_status import ollama_running_summary

                live = ollama_running_summary(base)
                if live:
                    bits.append(live)
            return " | ".join(bits)

        with prog.waiting(wait_label, hint=wait_hint, status_fn=status_fn):
            result = analyze_structured(
                prompt,
                cfg.model,
                pass_id=deep_pass.name,
                progress=prog,
                raw_dir=raw_dir,
                on_delta=gen.note_delta,
            )
        gen.mark_done()
        if result.layer == "degraded":
            prog.phase(
                f"LLM: pass {deep_pass.name} degraded — merging partial/empty result"
            )
        if result.report is None:
            parts.append(
                FindingReport(
                    confidence=0,
                    summary=Summary(),
                    issues=[],
                    durabilityGaps=[f"llm.schema_invalid:{deep_pass.name}"],
                )
            )
        else:
            parts.append(result.report)
        all_coverage_ids.extend(deep_pass.coverage_ids)

    report = merge_reports(parts, heur.issues)
    report.issues = coerce_issue_bands(report.issues)
    # Deduplicate coverage id list while preserving order
    seen_ids: set[str] = set()
    unique_ids: list[str] = []
    for cid in all_coverage_ids:
        if cid not in seen_ids:
            seen_ids.add(cid)
            unique_ids.append(cid)

    coverage = evaluate_coverage(unique_ids, report.issues, report.durabilityGaps)
    report.coverage = CoverageBlock(
        covered=list(coverage.covered),
        na=dict(coverage.na),
        missed=list(coverage.missed),
    )
    from repolens.themes import build_theme_breakdown

    report.themes = build_theme_breakdown(
        coverage,
        report.issues,
        mode=mode,
        full_audit=full_audit,
    )
    pass_confidences: dict[str, int] = {}
    for deep_pass, part in zip(passes, parts, strict=False):
        pass_confidences[deep_pass.name] = part.confidence
    report = _apply_coverage_metrics(
        report,
        coverage,
        pass_confidences=pass_confidences,
        scanner_runs=scanner_runs,
    )
    if unique_ids:
        prog.phase(
            f"Coverage: {len(coverage.covered)} covered · "
            f"{len(coverage.na)} N/A · {len(coverage.missed)} missed"
        )
        metric_bits = [f"gate {report.confidence}%"]
        if report.securityAuditConfidence is not None:
            metric_bits.append(f"security audit {report.securityAuditConfidence}%")
        if report.reliabilityAuditConfidence is not None:
            metric_bits.append(
                f"reliability audit {report.reliabilityAuditConfidence}%"
            )
        if report.architectureAuditConfidence is not None:
            metric_bits.append(
                f"architecture audit {report.architectureAuditConfidence}%"
            )
        prog.phase("Metrics: " + " · ".join(metric_bits))
    return report


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
