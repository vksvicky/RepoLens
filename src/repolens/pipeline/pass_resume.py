"""Resume a finished deep pass and keep the passes that already finished."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from repolens.config import RepoLensConfig
from repolens.deep import DeepPass, merge_reports
from repolens.llm.model_lock import bind_lock_context, reset_lock_context
from repolens.pipeline.deep_pass import _run_deep_pass
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
) -> tuple[FindingReport, str, bool, int]:
    label = pass_label(deep_pass.name)
    key = pass_key(deep_pass.files, model_name, deep_pass.name)
    cached = load_pass(root, key)
    if cached is not None:
        prog.phase(
            f"[Slow Brain] Resumed {label} from cache ({len(cached.issues)} findings)"
        )
        return cached, "", False, 0
    token = bind_lock_context(
        repo=root.name,
        path=str(root),
        pass_name=label,
        status=prog.phase,
    )
    try:
        part, raw, degraded, attempts = _run_deep_pass(
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
    if not degraded:
        save_pass(root, key, part)
    return part, raw, degraded, attempts
