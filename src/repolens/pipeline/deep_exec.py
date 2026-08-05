"""Deep multi-pass analysis and coverage metric application."""

from __future__ import annotations

from pathlib import Path

from repolens.adaptive import sync_project_fingerprints
from repolens.bands import coerce_issue_bands
from repolens.config import RepoLensConfig
from repolens.coverage import (
    CoverageResult,
    evaluate_coverage,
    is_lazy_na_reason,
    parse_coverage_notes,
)
from repolens.deep import build_deep_prompt, merge_reports, plan_deep_passes
from repolens.heuristics import run_heuristics
from repolens.inventory import FileEntry
from repolens.llm import default_model, resolve_llm_timeout
from repolens.metrics import compute_audit_metrics
from repolens.pipeline.prompt import _append_source_files
from repolens.progress import LlmGenerateProgress, ReviewProgress
from repolens.rules.registry import Rule, load_enabled_rules
from repolens.schema import CoverageBlock, FindingReport, ScannerRun, Summary


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
    from repolens.fp_calibrations import apply_fp_calibrations

    # Calibrate LLM-merged issues only (heuristics are already mixed in;
    # calibrations match injection/subprocess text patterns, not heuristic cats).
    report.issues = apply_fp_calibrations(report.issues, cfg.deep)
    report.summary = report.recount_summary()
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

