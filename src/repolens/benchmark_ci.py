"""Scanners-only benchmark control. Token totals are a measured zero."""

from __future__ import annotations

from pathlib import Path

from repolens.config import RepoLensConfig
from repolens.schema import FindingReport

FIXTURE_FILES = (
    "app.py",
    "clock.py",
    "labels.py",
    "main.py",
    "names.py",
    "note.py",
    "parse.py",
    "store.py",
    "total.py",
    "view.py",
)


def ci_control_row(
    report: FindingReport,
    *,
    label: str,
    fixture: str,
) -> dict[str, object]:
    """A scanners-only run. Zeros are measured because no model was called."""
    provenance = report.provenance
    rss = None if provenance is None else provenance.pythonPeakRssBytes
    fast_brain = None if provenance is None else provenance.fastBrainSeconds
    row: dict[str, object] = {
        "schemaVersion": "1.0",
        "fixture": fixture,
        "arm": "ci",
        "label": label,
        "model": None,
        "provider": None,
        "wallSeconds": report.durationSeconds,
        "promptChars": 0,
        "tokenSource": "none",
        "pythonPeakRssBytes": rss,
        "fastBrainSeconds": fast_brain,
        "scannerSeconds": _scanner_seconds(report),
        "firstTokenSeconds": 0,
        "generationSeconds": 0,
        "outputChars": 0,
        "charsPerSecond": 0,
        "queueWaitSeconds": 0,
        "resumedPasses": 0,
        "promptTokens": 0,
        "completionTokens": 0,
        "totalTokens": 0,
        "repairPromptTokens": 0,
        "repairCompletionTokens": 0,
        "repairCalls": 0,
        "missing": [],
    }
    return row


def run_ci_arm(path: Path, cfg: RepoLensConfig, out_dir: Path) -> FindingReport:
    """Review with scanners and Fast Brain. The model is not called."""
    from repolens.pipeline.review_state import ReviewRun
    from repolens.pipeline.run import run_review
    from repolens.progress import ReviewProgress

    report_dir = out_dir.resolve()
    result = run_review(ReviewRun(
        path=path,
        mode="sentinel",
        config=cfg,
        scanners="auto",
        scanners_only=True,
        deep=False,
        model_lock=False,
        resume=False,
        progress=ReviewProgress(verbose=True),
        out_dir=report_dir,
    ))
    return result.report


def _scanner_seconds(report: FindingReport) -> float:
    durations = [
        row.durationSeconds
        for row in report.scannerRuns
        if row.status == "ran" and row.durationSeconds is not None
    ]
    if not durations:
        return 0.0
    return round(sum(durations), 1)
