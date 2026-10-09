"""Resume a finished deep pass and keep the passes that already finished."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from repolens.config import RepoLensConfig
from repolens.deep import DeepPass, merge_reports
from repolens.llm.model_lock import (
    bind_lock_context,
    queue_wait_seconds,
    reset_lock_context,
)
from repolens.pipeline.deep_pass import _run_deep_pass
from repolens.pipeline.journal import append_event
from repolens.pipeline.pass_cache import load_pass, pass_key, pass_label, save_pass
from repolens.pipeline.types import ReviewAborted
from repolens.progress import ReviewProgress
from repolens.rules.registry import Rule
from repolens.schema import FindingReport, Issue, Summary


def snapshot_finished(
    report: FindingReport,
    out_dir: Path | None,
    fmt: str,
    finished_labels: list[str],
    mode: str,
    report_when: datetime | None,
) -> None:
    if out_dir is None or report_when is None or not finished_labels:
        return
    write_partial_report(
        report,
        out_dir,
        fmt=fmt,
        finished_labels=finished_labels,
        mode=mode,
        when=report_when,
    )


def write_partial_report(
    report: FindingReport,
    out_dir: Path,
    *,
    fmt: str,
    finished_labels: list[str],
    mode: str,
    when: datetime,
) -> None:
    snapshot = report.model_copy(deep=True)
    saved = ", ".join(finished_labels) or "none"
    snapshot.durabilityGaps.append(f"Finished passes are kept: {saved}.")
    from repolens.report import write_json_report, write_markdown_report

    if fmt in {"md", "both"}:
        write_markdown_report(snapshot, out_dir, mode=mode, when=when)
    if fmt in {"json", "both"}:
        write_json_report(snapshot, out_dir, mode=mode, when=when)


def raise_aborted(
    parts: list[FindingReport],
    heur_issues: list[Issue],
    finished_labels: list[str],
    *,
    root: Path | None = None,
) -> None:
    report = (
        merge_reports(parts, heur_issues)
        if parts
        else FindingReport(confidence=0, summary=Summary(), issues=[])
    )
    saved = ", ".join(finished_labels) or "none"
    report.durabilityGaps.append(
        f"Aborted by user. Finished passes are kept: {saved}."
    )
    if root is not None:
        append_event(
            root,
            "interrupted",
            finished=finished_labels,
            last_finished=finished_labels[-1] if finished_labels else None,
        )
    raise ReviewAborted(report)


def note_timed_out_passes(
    report: FindingReport,
    timed_out: list[str],
    finished: list[str],
) -> FindingReport:
    if not timed_out:
        return report
    named = ", ".join(timed_out)
    noun = "pass" if len(timed_out) == 1 else "passes"
    saved = ", ".join(finished) or "none"
    report.durabilityGaps.append(
        f"The {named} {noun} timed out. "
        f"This report includes the passes that finished ({saved}). "
        "Re-run when the model is free. Finished passes are kept."
    )
    return report


def _pass_cache_key(
    deep_pass: DeepPass,
    model_name: str,
    prior_summary: str,
) -> str:
    return pass_key(
        deep_pass.files,
        model_name,
        deep_pass.name,
        prior_summary=prior_summary or None,
        pack_mode=getattr(deep_pass, "pack_mode", "full") or "full",
        file_pack_modes=getattr(deep_pass, "file_pack_modes", None) or None,
    )


def _return_cached_pass(
    *,
    root: Path,
    deep_pass: DeepPass,
    label: str,
    cached: FindingReport,
    prog: ReviewProgress,
) -> tuple[FindingReport, str, bool, int]:
    prog.phase(
        f"[Slow Brain] Resumed {label} from cache ({len(cached.issues)} findings)"
    )
    append_event(
        root,
        "pass_completed",
        role=deep_pass.name,
        label=label,
        resumed=True,
        findings_count=len(cached.issues),
        pass_duration_ms=0,
        queue_wait_ms=0,
        pack_mode=getattr(deep_pass, "pack_mode", "full"),
        files_count=len(deep_pass.files),
    )
    return cached, "", False, 0


def _execute_live_pass(
    *,
    root: Path,
    idx: int,
    n: int,
    deep_pass: DeepPass,
    label: str,
    key: str,
    rules: list[Rule],
    pack_ids: list[str],
    prompt_prefix: str,
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    raw_dir: Path,
    model_name: str,
    provider: str,
    timeout: float,
) -> tuple[FindingReport, str, bool, int]:
    wait_before = queue_wait_seconds()
    started = time.perf_counter()
    token = bind_lock_context(
        repo=root.name,
        path=str(root),
        pass_name=label,
        status=prog.phase,
    )
    try:
        part, raw, degraded, attempts, chars_in, chars_out = _run_deep_pass(
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
        )
    finally:
        reset_lock_context(token)
    pass_duration_ms = int((time.perf_counter() - started) * 1000)
    queue_wait_ms = int(max(0.0, queue_wait_seconds() - wait_before) * 1000)
    if not degraded:
        save_pass(root, key, part)
    append_event(
        root,
        "pass_completed",
        role=deep_pass.name,
        label=label,
        resumed=False,
        degraded=degraded,
        findings_count=len(part.issues),
        chars_in=chars_in,
        chars_out=chars_out,
        pass_duration_ms=pass_duration_ms,
        queue_wait_ms=queue_wait_ms,
        pack_mode=getattr(deep_pass, "pack_mode", "full"),
        files_count=len(deep_pass.files),
        coverage_gap_count=sum(
            1 for gap in part.durabilityGaps if gap.startswith("coverage:")
        ),
    )
    if chars_in or chars_out:
        prog.detail(
            f"{label}: chars_in={chars_in:,} chars_out={chars_out:,} "
            f"(honesty metric; not a Metis % claim)"
        )
    return part, raw, degraded, attempts


def run_or_resume_pass(
    *,
    root: Path,
    idx: int,
    n: int,
    deep_pass: DeepPass,
    rules: list[Rule],
    pack_ids: list[str],
    prompt_prefix: str,
    cfg: RepoLensConfig,
    prog: ReviewProgress,
    raw_dir: Path,
    model_name: str,
    provider: str,
    timeout: float,
    prior_summary: str = "",
    skip_cache: bool = False,
) -> tuple[FindingReport, str, bool, int]:
    label = pass_label(deep_pass.name)
    key = _pass_cache_key(deep_pass, model_name, prior_summary)
    append_event(
        root,
        "pass_started",
        role=deep_pass.name,
        label=label,
        model=model_name,
        files_count=len(deep_pass.files),
        char_budget=cfg.deep.chars_per_pass,
        pack_mode=getattr(deep_pass, "pack_mode", "full"),
        role_packs=bool(cfg.deep.role_packs),
    )
    cached = None if skip_cache else load_pass(root, key)
    if cached is not None:
        return _return_cached_pass(
            root=root,
            deep_pass=deep_pass,
            label=label,
            cached=cached,
            prog=prog,
        )
    return _execute_live_pass(
        root=root,
        idx=idx,
        n=n,
        deep_pass=deep_pass,
        label=label,
        key=key,
        rules=rules,
        pack_ids=pack_ids,
        prompt_prefix=prompt_prefix,
        cfg=cfg,
        prog=prog,
        raw_dir=raw_dir,
        model_name=model_name,
        provider=provider,
        timeout=timeout,
    )
