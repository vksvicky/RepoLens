"""Markdown / JSON report writers."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from repolens.coverage import parse_coverage_notes
from repolens.disclaimer import disclaimer_markdown_lines
from repolens.schema import FindingReport, Issue, Severity

_FENCED_BLOCK_RE = re.compile(
    r"^\s*```[^\n]*\n(?P<body>.*?)\n```\s*$",
    re.DOTALL,
)

# Coverage N/A / missed notes travel in durabilityGaps for evaluation, but are not
# actionable "durability" todos — keep them out of the checkbox section.
_COVERAGE_TRANSPORT_GAP_RE = re.compile(
    r"^coverage:\S+\s*:\s*(N/A|missed)\b",
    re.IGNORECASE,
)


def report_timestamp(when: datetime | None = None) -> datetime:
    """Local clock used for report filenames and headings."""
    return when or datetime.now().astimezone()


def report_stamp(when: datetime | None = None) -> str:
    """Filesystem-safe stamp: ``YYYY-MM-DD_HHMM`` (avoids same-day overwrites)."""
    return report_timestamp(when).strftime("%Y-%m-%d_%H%M")


def report_heading_time(when: datetime | None = None) -> str:
    """Human-readable local time for the report title: ``YYYY-MM-DD HH:MM``."""
    return report_timestamp(when).strftime("%Y-%m-%d %H:%M")


def format_duration(seconds: float | None) -> str | None:
    """Human-readable wall-clock duration for report headers."""
    if seconds is None:
        return None
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s ({total}s)"
    if minutes:
        return f"{minutes}m {secs}s ({total}s)"
    return f"{secs}s"


def report_basename(mode: str, when: datetime | None = None) -> str:
    """Report stem including mode so sentinel/review/architecture do not collide.

    Example: ``gate_review_report_sentinel_2026-08-05_1430``
    """
    safe = mode.strip().lower().replace(" ", "_") or "review"
    return f"gate_review_report_{safe}_{report_stamp(when)}"


def write_markdown_report(
    report: FindingReport,
    out_dir: Path,
    *,
    mode: str = "review",
    commit_go: str = "n/a",
    push_go: str = "n/a",
    when: datetime | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report_basename(mode, when)}.md"
    path.write_text(
        render_markdown(
            report, mode=mode, commit_go=commit_go, push_go=push_go, when=when
        ),
        encoding="utf-8",
    )
    return path


def write_json_report(
    report: FindingReport,
    out_dir: Path,
    *,
    mode: str = "review",
    when: datetime | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report_basename(mode, when)}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def render_markdown(
    report: FindingReport,
    *,
    mode: str,
    commit_go: str,
    push_go: str,
    when: datetime | None = None,
) -> str:
    heading_time = report_heading_time(when)
    lines: list[str] = [
        f"# Gate review report — {heading_time}",
        "",
        f"**Mode:** `{mode}`",
        f"**Generated:** {heading_time}",
    ]
    duration = format_duration(report.durationSeconds)
    if duration is not None:
        lines.append(f"**Duration:** {duration}")
    lines.extend(
        [
            f"**Gate confidence:** {report.confidence}%",
            f"**Commit go/no-go:** {commit_go}",
            f"**Push go/no-go:** {push_go}",
            "",
            "## Gate verdict",
            "",
            f"- **Gate confidence:** {report.confidence}% "
            "(adequacy of this review package — not “% secure”)",
            (
                f"- **Counts:** Critical {report.summary.critical} · "
                f"High {report.summary.high} · Medium {report.summary.medium} · "
                f"Low {report.summary.low}"
            ),
        ]
    )
    if getattr(report, "llmReusedFrom", None):
        lines.append(
            f"- **LLM:** reused from last successful AI pass "
            f"(`{report.llmReusedFrom}`) — not a fresh deep review"
        )
    elif getattr(report, "llmSkipped", False):
        lines.append(
            "- **LLM:** skipped (no fingerprint delta under `--changed` and "
            "no prior LLM snapshot to reuse)"
        )
    lines.append("")
    lines.extend(_render_metrics_section(report))

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

    lines.extend(_render_durability_gaps_section(report))

    lines.extend(_render_coverage_section(report))
    lines.extend(_render_theme_breakdown(report))

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

    lines.extend(disclaimer_markdown_lines())
    return "\n".join(lines)


def is_coverage_transport_gap(gap: str) -> bool:
    """True when a gap is a coverage N/A or missed note (not a real durability todo)."""
    return bool(_COVERAGE_TRANSPORT_GAP_RE.match(gap.strip()))


def _render_durability_gaps_section(report: FindingReport) -> list[str]:
    """Render actionable durability gaps as checkboxes; omit coverage transport notes."""
    real_gaps = [
        g for g in report.durabilityGaps if not is_coverage_transport_gap(g)
    ]
    lines: list[str] = ["## Durability gaps", ""]
    if real_gaps:
        for gap in real_gaps:
            lines.append(f"- [ ] {gap}")
    else:
        lines.append("_None called out._")
    lines.append("")
    return lines


def _render_metrics_section(report: FindingReport) -> list[str]:
    """Glossary + band audit confidences (Phase 5.1)."""
    if (
        report.securityAuditConfidence is None
        and report.architectureAuditConfidence is None
        and report.reliabilityAuditConfidence is None
    ):
        return []
    lines = [
        "## Metrics",
        "",
        "| Metric | Value | Meaning |",
        "|--------|-------|---------|",
        (
            f"| Gate confidence | {report.confidence}% | How adequate this review "
            "package is for a gate decision — **not** “% secure” |"
        ),
    ]
    if report.securityAuditConfidence is not None:
        lines.append(
            f"| Security audit confidence | {report.securityAuditConfidence}% | "
            "Checklist honesty for P1 / `sec.*` **minus** open Critical/High "
            "security findings — **not** a vibes-style posture score |"
        )
    if report.reliabilityAuditConfidence is not None:
        lines.append(
            f"| Reliability audit confidence | {report.reliabilityAuditConfidence}% | "
            "Honesty/completeness of P2 / `rel.*` checklist |"
        )
    if report.architectureAuditConfidence is not None:
        lines.append(
            f"| Architecture audit confidence | {report.architectureAuditConfidence}% | "
            "Honesty/completeness of P3 / `arch.*` checklist |"
        )
    lines.extend(
        [
            "| Severity counts | (above) | Finding tallies — independent of confidence % |",
            "| Coverage | (below) | covered / N/A / missed checklist ids |",
            "",
        ]
    )
    return lines


def _render_coverage_section(report: FindingReport) -> list[str]:
    """Render checklist coverage when deep-mode coverage or coverage gaps exist."""
    cov = report.coverage
    na_from_gaps = parse_coverage_notes(report.durabilityGaps)
    missed_from_gaps = [
        g.split(":", 2)[1]
        for g in report.durabilityGaps
        if g.startswith("coverage:") and "missed" in g.lower()
    ]

    if cov is None and not na_from_gaps and not missed_from_gaps:
        return []

    covered = list(cov.covered) if cov is not None else []
    na = dict(cov.na) if cov is not None else dict(na_from_gaps)
    if cov is None:
        for cid, reason in na_from_gaps.items():
            na.setdefault(cid, reason)
    missed = list(cov.missed) if cov is not None else list(missed_from_gaps)

    lines: list[str] = [
        "## Coverage",
        "",
        (
            f"- **Covered:** {len(covered)} · **N/A:** {len(na)} · "
            f"**Missed:** {len(missed)}"
        ),
        "",
    ]
    if covered:
        lines.append("### Covered")
        lines.append("")
        for cid in covered:
            lines.append(f"- `{cid}`")
        lines.append("")
    if na:
        lines.append("### N/A")
        lines.append("")
        for cid, reason in na.items():
            lines.append(f"- `{cid}`: {reason}")
        lines.append("")
    if missed:
        lines.append("### Missed")
        lines.append("")
        for cid in missed:
            lines.append(f"- `{cid}`")
        lines.append("")
    return lines


def _render_theme_breakdown(report: FindingReport) -> list[str]:
    """Render Core / Extended theme table when themes are present (Phase 5.2)."""
    themes = report.themes
    if not themes:
        return []

    core = [t for t in themes if t.pack == "core"]
    extended = [t for t in themes if t.pack == "extended"]
    lines: list[str] = ["## Theme breakdown", ""]

    def _table(rows: list) -> list[str]:
        out = [
            "| Theme | Coverage | Findings | Notes |",
            "|-------|----------|----------|-------|",
        ]
        for t in rows:
            notes = (t.notes or "").replace("|", "\\|")
            out.append(
                f"| {t.title} | {t.status} | {t.findingCount} | {notes} |"
            )
        out.append("")
        return out

    if core:
        lines.append("### Core")
        lines.append("")
        lines.extend(_table(core))
    if extended:
        lines.append("### Extended")
        lines.append("")
        lines.extend(_table(extended))
    return lines


def render_code_example_fenced(code_example: str) -> list[str]:
    """Return Markdown lines for a code example without nested fence breakage.

    LLMs often return examples already wrapped in `` ```lang … ``` ``. Wrapping
    those again with `` ``` `` breaks CommonMark. Strip a single outer fence,
    then wrap with a fence longer than any run of backticks in the body.
    """
    text = code_example.strip("\n")
    match = _FENCED_BLOCK_RE.match(text)
    if match:
        body = match.group("body").rstrip("\n")
    else:
        body = text.rstrip("\n")
        # Defensive: drop a lone leading/trailing fence line if present.
        lines = body.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        body = "\n".join(lines).rstrip("\n")

    longest = 0
    for line in body.splitlines():
        run = 0
        for ch in line:
            if ch == "`":
                run += 1
                longest = max(longest, run)
            else:
                run = 0
    fence = "`" * max(3, longest + 1)
    return [fence, body, fence] if body else [fence, fence]


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
        block.extend(render_code_example_fenced(issue.codeExample))
    elif issue.severity in {Severity.CRITICAL, Severity.HIGH}:
        block.append("- **Code example:** _MISSING (invalid for Critical/High)_")
    return block
