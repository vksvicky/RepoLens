"""Plan deep passes and drive per-pass LLM execution."""

from __future__ import annotations

import logging
from pathlib import Path

from repolens.adaptive import sync_project_fingerprints
from repolens.config import RepoLensConfig
from repolens.deep_plan import PlanDeepPasses
from repolens.heuristics import HeuristicResult, run_heuristics
from repolens.heuristics.runner import RunHeuristics
from repolens.inventory import FileEntry
from repolens.pipeline.deep_job import DeepJob
from repolens.progress import ReviewProgress

_DIFF_PREVIEW = 8


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
        from repolens.inventory import classify_fingerprint_deletions

        store = ProjectStore(root)
        store.open()
        diff = sync_project_fingerprints(store, files)
        removed, dropped = classify_fingerprint_deletions(root, list(diff.deleted))
        bits = [
            f"+{len(diff.added)} added",
            f"~{len(diff.changed)} changed",
        ]
        if removed:
            bits.append(f"-{len(removed)} removed from tree")
        if dropped:
            bits.append(f"{len(dropped)} dropped from inventory pack")
        if not removed and not dropped:
            bits.append("-0 removed from tree")
        prog.phase("Cache: " + ", ".join(bits))
        if prog.verbose and (diff.added or diff.changed or removed or dropped):
            if diff.added:
                prog.detail("added: " + ", ".join(diff.added[:_DIFF_PREVIEW]))
            if diff.changed:
                prog.detail("changed: " + ", ".join(diff.changed[:_DIFF_PREVIEW]))
            if removed:
                prog.detail("removed from tree: " + ", ".join(removed[:_DIFF_PREVIEW]))
            if dropped:
                prog.detail(
                    "dropped from inventory pack (still on disk; over max_files): "
                    + ", ".join(dropped[:_DIFF_PREVIEW])
                )
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
            from repolens.inventory import FTS_CHUNK_CHARS, read_prefix

            text = read_prefix(entry.path, FTS_CHUNK_CHARS)[:FTS_CHUNK_CHARS]
        except OSError:
            logging.getLogger(__name__).debug("handled expected error", exc_info=True)
            continue
        store.upsert_chunk(entry.relative, text)


def _load_deep_heuristics(
    *,
    root: Path,
    files: list[FileEntry],
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    heur_result: HeuristicResult | None,
    pack_ids: list,
) -> HeuristicResult:
    if heur_result is not None:
        prog.phase("→ Deep: using Fast Brain heuristics…")
        heur = heur_result
    else:
        prog.phase("→ Deep: heuristics…")
        heur = run_heuristics(RunHeuristics(
        root=root,
        entries=files,
        mega_file_lines=cfg.deep.mega_file_lines,
        mega_file_exclude_globs=cfg.deep.extra_skip_globs() or None,
        pack_ids=pack_ids or None,
        workers=cfg.fast_brain.parallel_workers,
        near_clones_config=cfg.fast_brain.near_clones,
    ))
    if prog.verbose:
        prog.detail(f"heuristics: {len(heur.issues)} issue(s), {len(heur.hot_paths)} hot path(s)")
    return heur


def _announce_deep_runtime(prog: ReviewProgress, passes: list, cfg: RepoLensConfig) -> None:
    if prog.quiet or not passes:
        return
    from repolens.runtime_estimate import estimate_deep_runtime

    est = estimate_deep_runtime(
        files=len(passes[0].files) if passes else 0,
        passes=len(passes),
        provider=cfg.model.provider or "unknown",
    )
    prog.phase(est)
    if cfg.deep.role_packs:
        modes = ", ".join(f"{p.name}:{getattr(p, 'pack_mode', 'full')}" for p in passes)
        prog.detail(
            f"role_packs on — per-band file lists; pack modes [{modes}]; "
            "rolling prior-pass summary between bands"
        )


def _journal_review_started(root: Path, cfg: RepoLensConfig) -> None:
    from datetime import UTC, datetime

    from repolens.llm import default_model
    from repolens.pipeline.journal import append_event

    append_event(
        root,
        "review_started",
        run_id=datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ"),
        model=cfg.model.model or default_model(cfg.model.provider),
        role_packs=bool(cfg.deep.role_packs),
        provider=cfg.model.provider,
    )


def _prepare_deep_plan(job: DeepJob) -> tuple:
    root = job.root
    mode = job.mode
    full_audit = job.full_audit
    files = job.files
    llm_files = job.llm_files
    cfg = job.cfg
    prog = job.prog
    heur_result = job.heur_result
    graph = job.graph
    from repolens.deep import plan_deep_passes
    from repolens.rules.registry import Rule, load_enabled_rules

    pack_ids = list(cfg.packs.resolved())
    heur = _load_deep_heuristics(
        root=root,
        files=files,
        cfg=cfg,
        prog=prog,
        heur_result=heur_result,
        pack_ids=pack_ids,
    )
    rules: list[Rule] = load_enabled_rules(project_root=root)
    p3_gaps: list[str] = []
    passes = plan_deep_passes(PlanDeepPasses(
        mode=mode,
        full_audit=full_audit,
        entries=llm_files or files,
        hot_paths=heur.hot_paths,
        adaptive_paths=[e.relative for e in llm_files],
        chars_per_pass=cfg.deep.chars_per_pass,
        rules=rules,
        max_passes=cfg.deep.max_passes,
        role_packs=bool(cfg.deep.role_packs),
        graph=graph,
        durability_gaps_out=p3_gaps,
    ))
    return heur, rules, passes, p3_gaps, pack_ids


def _record_one_planned_pass(job: DeepJob) -> tuple[int, str]:
    deep_pass = job.deep_pass
    part = job.part
    raw = job.raw
    degraded = job.degraded
    attempts = job.attempts
    parts = job.parts
    raw_by_pass = job.raw_by_pass
    degraded_by_pass = job.degraded_by_pass
    all_coverage_ids = job.all_coverage_ids
    finished_labels = job.finished_labels
    timed_out_labels = job.timed_out_labels
    heur_issues = job.heur_issues
    out_dir = job.out_dir
    fmt = job.fmt
    mode = job.mode
    report_when = job.report_when
    cfg = job.cfg
    prior_summary = job.prior_summary
    from repolens.deep import merge_reports
    from repolens.pipeline.pass_cache import pass_label
    from repolens.pipeline.pass_resume import snapshot_finished

    parts.append(part)
    raw_by_pass[deep_pass.name] = raw
    degraded_by_pass[deep_pass.name] = degraded
    all_coverage_ids.extend(deep_pass.coverage_ids)
    label = pass_label(deep_pass.name)
    if degraded and any("timed out" in gap.lower() for gap in part.durabilityGaps):
        timed_out_labels.append(label)
    elif not degraded:
        finished_labels.append(label)
        snapshot_finished(
            merge_reports(parts, heur_issues),
            out_dir,
            fmt,
            finished_labels,
            mode,
            report_when,
        )
    next_prior = prior_summary
    if cfg.deep.role_packs and not degraded:
        from repolens.deep import compact_pass_summary

        next_prior = compact_pass_summary(part)
    return attempts, next_prior


def _prefix_with_prior(prompt_prefix: str, prior_summary: str, *, role_packs: bool) -> str:
    if not (role_packs and prior_summary):
        return prompt_prefix
    block = "## Prior pass findings (compact)\n" + prior_summary
    return f"{prompt_prefix}\n\n{block}" if prompt_prefix else block


def _run_and_record_planned_pass(job: DeepJob) -> tuple[int, str]:
    root = job.root
    idx = job.idx
    n = job.n
    deep_pass = job.deep_pass
    rules = job.rules
    pack_ids = job.pack_ids
    prompt_prefix = job.prompt_prefix
    cfg = job.cfg
    prog = job.prog
    raw_dir = job.raw_dir
    model_name = job.model_name
    provider = job.provider
    timeout = job.timeout
    prior_summary = job.prior_summary
    skip_cache = job.skip_cache
    parts = job.parts
    raw_by_pass = job.raw_by_pass
    degraded_by_pass = job.degraded_by_pass
    all_coverage_ids = job.all_coverage_ids
    finished_labels = job.finished_labels
    timed_out_labels = job.timed_out_labels
    heur_issues = job.heur_issues
    out_dir = job.out_dir
    fmt = job.fmt
    mode = job.mode
    report_when = job.report_when
    files_done = job.files_done
    files_total = job.files_total
    from repolens.pipeline.pass_resume import run_or_resume_pass

    prefix = _prefix_with_prior(prompt_prefix, prior_summary, role_packs=cfg.deep.role_packs)
    part, raw, degraded, attempts = run_or_resume_pass(DeepJob(
        root=root,
        idx=idx,
        n=n,
        deep_pass=deep_pass,
        rules=rules,
        pack_ids=pack_ids,
        prompt_prefix=prefix,
        cfg=cfg,
        prog=prog,
        raw_dir=raw_dir,
        model_name=model_name,
        provider=provider,
        timeout=timeout,
        prior_summary=prior_summary if cfg.deep.role_packs else "",
        skip_cache=skip_cache,
        files_done=files_done,
        files_total=files_total,
    ))
    return _record_one_planned_pass(DeepJob(
        deep_pass=deep_pass,
        part=part,
        raw=raw,
        degraded=degraded,
        attempts=attempts,
        parts=parts,
        raw_by_pass=raw_by_pass,
        degraded_by_pass=degraded_by_pass,
        all_coverage_ids=all_coverage_ids,
        finished_labels=finished_labels,
        timed_out_labels=timed_out_labels,
        heur_issues=heur_issues,
        out_dir=out_dir,
        fmt=fmt,
        mode=mode,
        report_when=report_when,
        cfg=cfg,
        prior_summary=prior_summary,
    ))


def _drive_planned_passes(job: DeepJob) -> int:
    root = job.root
    passes = job.passes
    rules = job.rules
    pack_ids = job.pack_ids
    prompt_prefix = job.prompt_prefix
    cfg = job.cfg
    prog = job.prog
    raw_dir = job.raw_dir
    skip_cache = job.skip_cache
    heur_issues = job.heur_issues
    out_dir = job.out_dir
    fmt = job.fmt
    mode = job.mode
    report_when = job.report_when
    parts = job.parts
    raw_by_pass = job.raw_by_pass
    degraded_by_pass = job.degraded_by_pass
    all_coverage_ids = job.all_coverage_ids
    finished_labels = job.finished_labels
    timed_out_labels = job.timed_out_labels
    retry_passes = job.retry_passes
    from repolens.llm import default_model, resolve_llm_timeout

    repair_attempts_total = 0
    prior_summary = ""
    files_total = sum(len(getattr(item, "files", []) or []) for item in passes)
    files_done = 0
    n = len(passes)
    provider = cfg.model.provider or "unknown"
    model_name = cfg.model.model or default_model(cfg.model.provider)
    timeout = resolve_llm_timeout(cfg.model)
    if retry_passes and not skip_cache:
        prog.detail(f"Retrying pass(es): {', '.join(sorted(retry_passes))}")
    for idx, deep_pass in enumerate(passes, start=1):
        added, prior_summary = _run_and_record_planned_pass(DeepJob(
            root=root,
            idx=idx,
            n=n,
            deep_pass=deep_pass,
            rules=rules,
            pack_ids=pack_ids,
            prompt_prefix=prompt_prefix,
            cfg=cfg,
            prog=prog,
            raw_dir=raw_dir,
            model_name=model_name,
            provider=provider,
            timeout=timeout,
            prior_summary=prior_summary,
            skip_cache=skip_cache or deep_pass.name in retry_passes,
            parts=parts,
            raw_by_pass=raw_by_pass,
            degraded_by_pass=degraded_by_pass,
            all_coverage_ids=all_coverage_ids,
            finished_labels=finished_labels,
            timed_out_labels=timed_out_labels,
            heur_issues=heur_issues,
            out_dir=out_dir,
            fmt=fmt,
            mode=mode,
            report_when=report_when,
            files_done=files_done,
            files_total=files_total,
        ))
        repair_attempts_total += added
        if not degraded_by_pass.get(deep_pass.name):
            files_done += len(getattr(deep_pass, "files", []) or [])
    return repair_attempts_total


def _note_resume_hint(root: Path, prog: ReviewProgress) -> None:
    from repolens.pipeline.pass_progress import continue_line

    text = continue_line(root)
    if text:
        prog.phase(text)
