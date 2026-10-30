"""Fast Brain before a commit. The report stays in a temporary directory."""

from __future__ import annotations

import tempfile
from pathlib import Path

from repolens.config import load_config
from repolens.pipeline.review_state import ReviewRun
from repolens.pipeline.run import run_review
from repolens.progress import ReviewProgress
from repolens.schema import Severity
from repolens.triage import fail_on_triggered

_RANK = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


def blocking_lines(root: Path) -> list[str]:
    """Run Fast Brain and return ``path:line: title`` for MEDIUM and above.

    An empty list means the hook passes. Heuristic findings count even when
    the project turns CI triage on. Scanner binaries are not run.
    """
    cfg = load_config(root)
    cfg.adaptive.enabled = False
    with tempfile.TemporaryDirectory(prefix="repolens-hook-") as tmp:
        result = run_review(ReviewRun(
            path=root,
            mode="review",
            out_dir=Path(tmp),
            fmt="json",
            scanners="off",
            scanners_only=True,
            deep=False,
            config=cfg,
            progress=ReviewProgress(quiet=True),
            record_last_report=False,
        ))
    if not fail_on_triggered(result.report, "MEDIUM", scanner_only=False):
        return []
    lines: list[str] = []
    for issue in result.report.issues:
        if _RANK[issue.severity] >= _RANK[Severity.MEDIUM]:
            lines.append(f"{issue.file}:{issue.line}: {issue.title}")
    return lines
