"""Plan deep passes and drive per-pass LLM execution."""

from __future__ import annotations

from pathlib import Path

from repolens.adaptive import sync_project_fingerprints
from repolens.config import RepoLensConfig
from repolens.heuristics import HeuristicResult, run_heuristics
from repolens.inventory import FileEntry
from repolens.progress import ReviewProgress
from repolens.schema import FindingReport


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
                prog.detail("added: " + ", ".join(diff.added[:8]))
            if diff.changed:
                prog.detail("changed: " + ", ".join(diff.changed[:8]))
            if removed:
                prog.detail("removed from tree: " + ", ".join(removed[:8]))
            if dropped:
                prog.detail(
                    "dropped from inventory pack (still on disk; over max_files): "
                    + ", ".join(dropped[:8])
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
            text = entry.path.read_text(encoding="utf-8", errors="replace")[:80_000]
        except OSError:
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
        heur = run_heuristics(
            root,
            files,
            mega_file_lines=cfg.deep.mega_file_lines,
            mega_file_exclude_globs=cfg.deep.extra_skip_globs() or None,
            pack_ids=pack_ids or None,
            workers=cfg.fast_brain.parallel_workers,
            near_clones_config=cfg.fast_brain.near_clones,
        )
    if prog.verbose:
        prog.detail(
            f"heuristics: {len(heur.issues)} issue(s), "
            f"{len(heur.hot_paths)} hot path(s)"
        )
    return heur


def _announce_deep_runtime(
    prog: ReviewProgress, passes: list, cfg: RepoLensConfig
) -> None:
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


def _prepare_deep_plan(
    *,
    root: Path,
    mode: str,
    full_audit: bool,
    files: list[FileEntry],
    llm_files: list[FileEntry],
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    heur_result: HeuristicResult | None,
    graph: object | None,
) -> tuple:
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
    passes = plan_deep_passes(
        mode,
        full_audit=full_audit,
        entries=llm_files or files,
        hot_paths=heur.hot_paths,
        adaptive_paths=[e.relative for e in llm_files],
        chars_per_pass=cfg.deep.chars_per_pass,
        rules=rules,
        max_passes=cfg.deep.max_passes,
        role_packs=bool(cfg.deep.role_packs),
        graph=graph,  # type: ignore[arg-type]
        durability_gaps_out=p3_gaps,
    )
    return heur, rules, passes, p3_gaps, pack_ids


def _record_one_planned_pass(
    *,
    deep_pass,
    part: FindingReport,
    raw: str,
    degraded: bool,
    attempts: int,
    parts: list[FindingReport],
    raw_by_pass: dict[str, str],
    degraded_by_pass: dict[str, bool],
    all_coverage_ids: list[str],
    finished_labels: list[str],
    timed_out_labels: list[str],
    heur_issues: list,
    out_dir: Path | None,
    fmt: str,
    mode: str,
    report_when: object | None,
    cfg: RepoLensConfig,
    prior_summary: str,
) -> tuple[int, str]:
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


def _run_and_record_planned_pass(
    *,
    root: Path,
    idx: int,
    n: int,
    deep_pass,
    rules: list,
    pack_ids: list[str],
    prompt_prefix: str,
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    raw_dir: Path,
    model_name: str,
    provider: str,
    timeout: float,
    prior_summary: str,
    skip_cache: bool,
    parts: list,
    raw_by_pass: dict,
    degraded_by_pass: dict,
    all_coverage_ids: list,
    finished_labels: list,
    timed_out_labels: list,
    heur_issues: list,
    out_dir: Path | None,
    fmt: str,
    mode: str,
    report_when: object | None,
) -> tuple[int, str]:
    from repolens.pipeline.pass_resume import run_or_resume_pass

    prefix = _prefix_with_prior(
        prompt_prefix, prior_summary, role_packs=cfg.deep.role_packs
    )
    part, raw, degraded, attempts = run_or_resume_pass(
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
    )
    return _record_one_planned_pass(
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
    )


def _drive_planned_passes(
    *,
    root: Path,
    passes: list,
    rules: list,
    pack_ids: list[str],
    prompt_prefix: str,
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    raw_dir: Path,
    skip_cache: bool,
    heur_issues: list,
    out_dir: Path | None,
    fmt: str,
    mode: str,
    report_when: object | None,
    parts: list,
    raw_by_pass: dict,
    degraded_by_pass: dict,
    all_coverage_ids: list,
    finished_labels: list,
    timed_out_labels: list,
    retry_passes: frozenset[str] = frozenset(),
) -> int:
    from repolens.llm import default_model, resolve_llm_timeout

    repair_attempts_total = 0
    prior_summary = ""
    n = len(passes)
    provider = cfg.model.provider or "unknown"
    model_name = cfg.model.model or default_model(cfg.model.provider)
    timeout = resolve_llm_timeout(cfg.model)
    if retry_passes and not skip_cache:
        prog.detail(f"Retrying pass(es): {', '.join(sorted(retry_passes))}")
    for idx, deep_pass in enumerate(passes, start=1):
        added, prior_summary = _run_and_record_planned_pass(
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
        )
        repair_attempts_total += added
    return repair_attempts_total


def _note_resume_hint(root: Path, skip_cache: bool, prog: ReviewProgress) -> None:
    if skip_cache:
        return
    from repolens.pipeline.journal import last_finished_label

    last = last_finished_label(root)
    if last:
        prog.detail(f"Resume: last finished pass in journal: {last}")
