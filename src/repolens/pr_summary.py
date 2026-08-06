"""PR-oriented summary + GitHub workflow annotations (Phase 6.8)."""

from __future__ import annotations

from pathlib import Path

from repolens.report import render_code_example_fenced
from repolens.schema import FindingReport, Issue, Severity

_MAX_EXAMPLE_LINES = 40
_MAX_ANNOTATIONS = 20
_MAX_TITLE = 120


def find_newest_report_json(out_dir: Path) -> Path | None:
    """Newest FindingReport JSON under ``out_dir`` (excludes ``*.sarif.json``)."""
    if not out_dir.is_dir():
        return None
    candidates = [
        p
        for p in out_dir.glob("gate_review_report_*.json")
        if not p.name.endswith(".sarif.json")
    ]
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _severity_rank(sev: Severity) -> int:
    return {
        Severity.CRITICAL: 4,
        Severity.HIGH: 3,
        Severity.MEDIUM: 2,
        Severity.LOW: 1,
    }[sev]


def _critical_high(report: FindingReport) -> list[Issue]:
    issues = [
        i
        for i in report.issues
        if i.severity in {Severity.CRITICAL, Severity.HIGH}
    ]
    return sorted(issues, key=lambda i: (-_severity_rank(i.severity), i.file, i.line))


def _safe_annotation_file(relative: str) -> str | None:
    """Return a workspace-relative path safe for ``file=``; else None."""
    rel = relative.replace("\\", "/").lstrip("./")
    if not rel or ".." in Path(rel).parts:
        return None
    if any(c in rel for c in "\n\r:"):
        return None
    return rel


def _escape_workflow(text: str) -> str:
    """Escape a workflow-command message (GitHub Actions)."""
    return (
        text.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
        .replace(":", "%3A")
    )


def _truncate_example(code: str) -> str:
    lines = code.splitlines()
    if len(lines) <= _MAX_EXAMPLE_LINES:
        return code
    kept = "\n".join(lines[:_MAX_EXAMPLE_LINES])
    return f"{kept}\n# … truncated ({len(lines) - _MAX_EXAMPLE_LINES} more line(s))"


def render_pr_summary(report: FindingReport) -> str:
    """Markdown suitable for ``$GITHUB_STEP_SUMMARY`` / PR body paste."""
    s = report.summary
    lines: list[str] = [
        "## RepoLens PR summary",
        "",
        f"**Gate confidence:** {report.confidence}%",
        (
            f"**Counts:** Critical {s.critical} · High {s.high} · "
            f"Medium {s.medium} · Low {s.low}"
        ),
    ]
    if report.llmBypassed:
        lines.append("**LLM:** bypassed (scanners clean at triage floor)")
    elif report.llmSkipped:
        lines.append("**LLM:** skipped (no fingerprint delta)")
    elif report.llmReusedFrom:
        lines.append(f"**LLM:** reused from `{report.llmReusedFrom}`")
    if report.suppressedIssues:
        lines.append(f"**Suppressed (audit):** {len(report.suppressedIssues)}")
    lines.extend(["", "### Suggested fixes (Critical / High)", ""])

    focus = _critical_high(report)
    if not focus:
        lines.append("_No Critical or High findings._")
        lines.append("")
        lines.append(
            "_Apply suggested fixes manually after review — RepoLens does not "
            "auto-commit changes._"
        )
        lines.append("")
        return "\n".join(lines)

    for issue in focus:
        lines.append(f"#### [{issue.severity.value}] {issue.title}")
        lines.append(f"- **Where:** `{issue.file}:{issue.line}`")
        if issue.stableId:
            lines.append(f"- **Stable ID:** `{issue.stableId}`")
        lines.append(f"- **Fix:** {issue.recommendedFix}")
        example = (issue.codeExample or "").strip()
        if example:
            lines.append("- **Example:**")
            lines.append("")
            lines.extend(render_code_example_fenced(_truncate_example(example)))
        lines.append("")

    lines.append(
        "_Apply suggested fixes manually after review — RepoLens does not "
        "auto-commit changes._"
    )
    lines.append("")
    return "\n".join(lines)


def render_workflow_annotations(
    report: FindingReport,
    *,
    max_annotations: int = _MAX_ANNOTATIONS,
) -> list[str]:
    """GitHub Actions workflow commands (``::error`` / ``::warning``)."""
    out: list[str] = []
    for issue in _critical_high(report)[:max_annotations]:
        level = "error" if issue.severity == Severity.CRITICAL else "warning"
        title = (issue.title or "finding")[:_MAX_TITLE]
        msg = _escape_workflow(f"[{issue.severity.value}] {title}")
        file_ = _safe_annotation_file(issue.file)
        if file_ is not None and issue.line >= 1:
            out.append(f"::{level} file={file_},line={issue.line}::{msg}")
        else:
            out.append(f"::{level}::{msg}")
    return out
