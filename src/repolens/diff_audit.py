"""Compare two FindingReport JSON files for drift (diff-audit)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from html import escape
from pathlib import Path

from repolens.schema import FindingReport, Issue


@dataclass
class DiffAuditResult:
    left: str
    right: str
    resolved: list[str] = field(default_factory=list)
    new: list[str] = field(default_factory=list)
    unchanged: int = 0
    left_confidence: int = 0
    right_confidence: int = 0
    confidence_delta: int = 0
    notes: list[str] = field(default_factory=list)
    cyclicity_left: int | None = None
    cyclicity_right: int | None = None
    complexity_issues_left: int | None = None
    complexity_issues_right: int | None = None
    max_cyclomatic_left: int | None = None
    max_cyclomatic_right: int | None = None


def _issue_key(issue: Issue) -> str:
    return f"{issue.file}:{issue.line}:{issue.title}"


def diff_audit_reports(left: FindingReport, right: FindingReport) -> DiffAuditResult:
    left_map = {_issue_key(i): i for i in left.issues}
    right_map = {_issue_key(i): i for i in right.issues}
    left_keys = set(left_map)
    right_keys = set(right_map)
    resolved = sorted(left_keys - right_keys)
    new = sorted(right_keys - left_keys)
    unchanged = len(left_keys & right_keys)
    notes: list[str] = []
    cyc_l = left.graph.cyclicity if left.graph else None
    cyc_r = right.graph.cyclicity if right.graph else None
    if cyc_l is not None and cyc_r is not None and cyc_l != cyc_r:
        notes.append(f"cyclicity drift: {cyc_l} → {cyc_r}")
    cx_l = left.complexity.issueCount if left.complexity else None
    cx_r = right.complexity.issueCount if right.complexity else None
    max_l = left.complexity.maxCyclomatic if left.complexity else None
    max_r = right.complexity.maxCyclomatic if right.complexity else None
    if cx_l is not None and cx_r is not None and cx_l != cx_r:
        notes.append(f"complexity issue count: {cx_l} → {cx_r}")
    if max_l is not None and max_r is not None and max_l != max_r:
        notes.append(f"max cyclomatic: {max_l} → {max_r}")
    return DiffAuditResult(
        left="",
        right="",
        resolved=resolved,
        new=new,
        unchanged=unchanged,
        left_confidence=int(left.confidence),
        right_confidence=int(right.confidence),
        confidence_delta=int(right.confidence) - int(left.confidence),
        notes=notes,
        cyclicity_left=cyc_l,
        cyclicity_right=cyc_r,
        complexity_issues_left=cx_l,
        complexity_issues_right=cx_r,
        max_cyclomatic_left=max_l,
        max_cyclomatic_right=max_r,
    )


def load_report(path: Path) -> FindingReport:
    return FindingReport.model_validate_json(path.read_text(encoding="utf-8"))


def diff_audit_files(left_path: Path, right_path: Path) -> DiffAuditResult:
    result = diff_audit_reports(load_report(left_path), load_report(right_path))
    result.left = str(left_path)
    result.right = str(right_path)
    return result


def diff_audit_as_dict(result: DiffAuditResult) -> dict:
    return asdict(result)


def _bullet_block(title: str, rows: list[str], *, empty: str) -> list[str]:
    lines = [f"## {title}", ""]
    if not rows:
        lines.append(empty)
        lines.append("")
        return lines
    for row in rows:
        lines.append(f"- {row}")
    lines.append("")
    return lines


def _debt_lines(result: DiffAuditResult) -> list[str]:
    lines = ["## Debt drift", ""]
    rows: list[str] = []
    if result.cyclicity_left is not None and result.cyclicity_right is not None:
        rows.append(
            f"Import cyclicity: **{result.cyclicity_left} → {result.cyclicity_right}**"
        )
    if (
        result.complexity_issues_left is not None
        and result.complexity_issues_right is not None
    ):
        rows.append(
            "Complexity issues: "
            f"**{result.complexity_issues_left} → {result.complexity_issues_right}**"
        )
    if (
        result.max_cyclomatic_left is not None
        and result.max_cyclomatic_right is not None
    ):
        rows.append(
            "Max cyclomatic: "
            f"**{result.max_cyclomatic_left} → {result.max_cyclomatic_right}**"
        )
    if not rows:
        lines.append("_No cyclicity or complexity signals on both reports._")
        lines.append("")
        return lines
    lines.extend(f"- {r}" for r in rows)
    lines.append("")
    return lines


def render_diff_audit_md(
    result: DiffAuditResult,
    *,
    left: FindingReport | None = None,
    right: FindingReport | None = None,
) -> str:
    """One-page client comparison Markdown."""
    _ = left, right  # reserved for future score tables
    lines = [
        "# Audit diff — client update",
        "",
        f"**Left:** `{result.left or 'earlier'}`  ",
        f"**Right:** `{result.right or 'later'}`  ",
        f"**Gate confidence:** {result.left_confidence}% → {result.right_confidence}% "
        f"(Δ {result.confidence_delta:+d})",
        "",
        f"Unchanged findings: **{result.unchanged}**",
        "",
    ]
    lines.extend(
        _bullet_block(
            "Closed findings",
            result.resolved,
            empty="_None closed between these two audits._",
        )
    )
    lines.extend(
        _bullet_block(
            "New regressions",
            result.new,
            empty="_No new findings between these two audits._",
        )
    )
    lines.extend(_debt_lines(result))
    if result.notes:
        lines.append("## Notes")
        lines.append("")
        for note in result.notes:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)


def render_diff_audit_html(
    result: DiffAuditResult,
    *,
    left: FindingReport | None = None,
    right: FindingReport | None = None,
) -> str:
    """One-page HTML suitable for email / client updates."""
    md = render_diff_audit_md(result, left=left, right=right)

    def ul(rows: list[str], empty: str) -> str:
        if not rows:
            return f"<p><em>{escape(empty)}</em></p>"
        items = "".join(f"<li>{escape(r)}</li>" for r in rows)
        return f"<ul>{items}</ul>"

    debt_bits = []
    if result.cyclicity_left is not None and result.cyclicity_right is not None:
        debt_bits.append(
            f"<li>Import cyclicity: <strong>{result.cyclicity_left} → "
            f"{result.cyclicity_right}</strong></li>"
        )
    if (
        result.complexity_issues_left is not None
        and result.complexity_issues_right is not None
    ):
        debt_bits.append(
            f"<li>Complexity issues: <strong>{result.complexity_issues_left} → "
            f"{result.complexity_issues_right}</strong></li>"
        )
    if (
        result.max_cyclomatic_left is not None
        and result.max_cyclomatic_right is not None
    ):
        debt_bits.append(
            f"<li>Max cyclomatic: <strong>{result.max_cyclomatic_left} → "
            f"{result.max_cyclomatic_right}</strong></li>"
        )
    debt_html = (
        f"<ul>{''.join(debt_bits)}</ul>"
        if debt_bits
        else "<p><em>No cyclicity or complexity signals on both reports.</em></p>"
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>Audit diff — client update</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 40rem; margin: 1.5rem auto;
       line-height: 1.4; }}
h1 {{ font-size: 1.35rem; }}
h2 {{ font-size: 1.05rem; margin-top: 1.25rem; border-bottom: 1px solid #ddd; }}
</style></head><body>
<h1>Audit diff — client update</h1>
<p><strong>Left:</strong> {escape(result.left or "earlier")}<br/>
<strong>Right:</strong> {escape(result.right or "later")}<br/>
<strong>Gate confidence:</strong> {result.left_confidence}% → {result.right_confidence}%
(Δ {result.confidence_delta:+d})<br/>
Unchanged findings: <strong>{result.unchanged}</strong></p>
<h2>Closed findings</h2>
{ul(result.resolved, "None closed between these two audits.")}
<h2>New regressions</h2>
{ul(result.new, "No new findings between these two audits.")}
<h2>Debt drift</h2>
{debt_html}
<!-- md-bytes {len(md)} -->
</body></html>
"""
