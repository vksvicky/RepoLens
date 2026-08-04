"""Markdown / JSON report writers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from repolens.schema import FindingReport, Issue, Severity


def write_markdown_report(
    report: FindingReport,
    out_dir: Path,
    *,
    mode: str = "review",
    commit_go: str = "n/a",
    push_go: str = "n/a",
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"gate_review_report_{date.today().isoformat()}.md"
    path.write_text(
        render_markdown(report, mode=mode, commit_go=commit_go, push_go=push_go),
        encoding="utf-8",
    )
    return path


def write_json_report(report: FindingReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"gate_review_report_{date.today().isoformat()}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def render_markdown(
    report: FindingReport,
    *,
    mode: str,
    commit_go: str,
    push_go: str,
) -> str:
    lines: list[str] = [
        f"# Gate review report — {date.today().isoformat()}",
        "",
        f"**Mode:** `{mode}`",
        f"**Confidence:** {report.confidence}%",
        f"**Commit go/no-go:** {commit_go}",
        f"**Push go/no-go:** {push_go}",
        "",
        "## Gate verdict",
        "",
        f"- **Confidence:** {report.confidence}%",
        (
            f"- **Counts:** Critical {report.summary.critical} · "
            f"High {report.summary.high} · Medium {report.summary.medium} · "
            f"Low {report.summary.low}"
        ),
        "",
    ]

    bands = (
        ("P1", "P1 — Security"),
        ("P2", "P2 — Bugs, reliability, performance"),
        ("P3", "P3 — Architecture & quality"),
    )
    for band, label in bands:
        band_issues = [i for i in report.issues if i.priority == band]
        lines.append(f"## {label}")
        lines.append("")
        if not band_issues:
            lines.append("_No findings in this band._")
            lines.append("")
            continue
        for issue in band_issues:
            lines.extend(_render_issue(issue))
            lines.append("")

    lines.extend(["## Automated scanners", ""])
    if report.scannerRuns:
        for run in report.scannerRuns:
            lines.append(
                f"- **{run.tool}**: `{run.status}`"
                + (f" — {run.detail}" if run.detail else "")
                + (f" ({run.findingCount} finding(s))" if run.status == "ran" else "")
            )
        lines.append("")
    else:
        lines.append("_No scanners requested or configured._")
        lines.append("")

    lines.extend(["## Plan to fix", ""])
    immediate = [i for i in report.issues if i.fixTiming == "immediately"]
    if immediate:
        for issue in immediate:
            lines.append(
                f"1. **{issue.title}** (`{issue.file}:{issue.line}`) — "
                f"{issue.recommendedFix}"
            )
    else:
        lines.append("_No immediate-priority findings._")
    lines.append("")

    lines.extend(["## Durability gaps", ""])
    if report.durabilityGaps:
        for gap in report.durabilityGaps:
            lines.append(f"- [ ] {gap}")
    else:
        lines.append("_None called out._")
    lines.append("")

    if report.scores is not None:
        s = report.scores
        lines.extend(
            [
                "## Architecture scores",
                "",
                "| Dimension | Score (1–10) |",
                "|-----------|--------------|",
                f"| Architecture | {s.architecture} |",
                f"| Security | {s.security} |",
                f"| Maintainability | {s.maintainability} |",
                f"| Performance | {s.performance} |",
                f"| Scalability | {s.scalability} |",
                f"| Production readiness | {s.productionReadiness} |",
                "",
            ]
        )

    return "\n".join(lines)


def _render_issue(issue: Issue) -> list[str]:
    block = [
        f"### [{issue.severity.value}] {issue.title}",
        f"- **Priority:** {issue.priority}",
        f"- **File:** `{issue.file}`",
        f"- **Line:** {issue.line}",
        f"- **Category:** {issue.category}",
        f"- **Explanation:** {issue.explanation}",
        f"- **Impact:** {issue.impact or '_n/a_'}",
        f"- **Recommended fix:** {issue.recommendedFix}",
        f"- **Fix timing:** {issue.fixTiming}",
    ]
    if issue.owasp:
        block.append(f"- **OWASP:** {issue.owasp}")
    if issue.cwe:
        block.append(f"- **CWE:** {issue.cwe}")
    if issue.codeExample.strip():
        block.append("- **Code example:**")
        block.append("")
        block.append("```")
        block.append(issue.codeExample.rstrip())
        block.append("```")
    elif issue.severity in {Severity.CRITICAL, Severity.HIGH}:
        block.append("- **Code example:** _MISSING (invalid for Critical/High)_")
    return block
