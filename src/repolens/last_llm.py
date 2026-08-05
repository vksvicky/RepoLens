"""Canonical last-successful-LLM report snapshot (empty --changed reuse)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from repolens.learning.store import ProjectStore
from repolens.report_parse import bootstrap_markdown_from_out_dir
from repolens.schema import FindingReport, Issue, ScannerRun, Summary

log = logging.getLogger(__name__)

META_REPORT = "last_llm_report_json"
META_SAVED_AT = "last_llm_saved_at"
META_MODEL = "last_llm_model"
META_MODE = "last_llm_mode"


def save_last_llm_report(
    store: ProjectStore,
    report: FindingReport,
    *,
    model: str | None,
    mode: str,
    when: datetime | None = None,
) -> None:
    """Persist a fresh LLM report as the project’s reuse snapshot."""
    if not report.llmCompleted or report.llmSkipped:
        return
    stamp = (when or datetime.now(timezone.utc)).isoformat()
    # Snapshot without this-run wall clock; reuse path sets duration anew.
    payload = report.model_copy(
        update={
            "durationSeconds": None,
            "llmSkipped": False,
            "llmReusedFrom": None,
            "llmCompleted": True,
        }
    )
    store.set_meta(META_REPORT, payload.model_dump_json())
    store.set_meta(META_SAVED_AT, stamp)
    store.set_meta(META_MODEL, model or "")
    store.set_meta(META_MODE, mode)


def load_last_llm_report(
    store: ProjectStore,
) -> tuple[FindingReport, str, str] | None:
    """Return (report, saved_at, model) or None."""
    raw = store.get_meta(META_REPORT)
    if not raw:
        return None
    try:
        report = FindingReport.model_validate_json(raw)
    except Exception as exc:  # noqa: BLE001 — corrupt meta should not abort review
        log.warning("Ignoring corrupt last_llm_report_json: %s", exc)
        return None
    saved_at = store.get_meta(META_SAVED_AT) or "unknown"
    model = store.get_meta(META_MODEL) or ""
    return report, saved_at, model


def bootstrap_from_out_dir(out_dir: Path | None) -> tuple[FindingReport, str, str] | None:
    """Prefer newest completed JSON; else richest markdown report (most findings)."""
    if out_dir is None or not out_dir.is_dir():
        return None
    candidates: list[tuple[float, Path]] = []
    for path in out_dir.glob("gate_review_report_*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not data.get("llmCompleted"):
            continue
        if data.get("llmSkipped"):
            continue
        candidates.append((path.stat().st_mtime, path))
    if candidates:
        candidates.sort(key=lambda t: t[0], reverse=True)
        path = candidates[0][1]
        try:
            report = FindingReport.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            log.warning("Bootstrap report unreadable %s: %s", path, exc)
        else:
            saved_at = datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat()
            return report, saved_at, ""

    md = bootstrap_markdown_from_out_dir(out_dir)
    if md is None:
        return None
    report, saved_at, model, path = md
    log.info("Bootstrapped last LLM findings from markdown %s", path.name)
    return report, saved_at, model


def issue_key(issue: Issue) -> tuple[str, int, str]:
    return (issue.file, issue.line, issue.title)


def merge_reused_report(
    prior: FindingReport,
    *,
    scanner_issues: list[Issue],
    scanner_runs: list[ScannerRun],
    scanner_gaps: list[str],
    saved_at: str,
    model: str,
) -> FindingReport:
    """Carry forward prior LLM findings; refresh scanners for this run."""
    seen = {issue_key(i) for i in prior.issues}
    merged_issues = list(prior.issues)
    for issue in scanner_issues:
        key = issue_key(issue)
        if key not in seen:
            merged_issues.append(issue)
            seen.add(key)

    reused_label = saved_at
    if model:
        reused_label = f"{saved_at} · {model}"

    confidence = max(int(prior.confidence) - 5, 40)
    gap = (
        f"LLM findings reused from last successful AI pass ({reused_label}). "
        "No fingerprint delta under --changed — not a fresh deep review. "
        "Use --full or edit files to run the model again."
    )
    report = FindingReport(
        confidence=confidence,
        summary=Summary(),
        issues=merged_issues,
        durabilityGaps=[gap] + list(scanner_gaps),
        scores=prior.scores,
        scannerRuns=list(scanner_runs),
        coverage=prior.coverage,
        themes=prior.themes,
        securityAuditConfidence=prior.securityAuditConfidence,
        architectureAuditConfidence=prior.architectureAuditConfidence,
        reliabilityAuditConfidence=prior.reliabilityAuditConfidence,
        llmSkipped=True,
        llmCompleted=False,
        llmReusedFrom=reused_label,
    )
    report.summary = report.recount_summary()
    return report
