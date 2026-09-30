"""Markdown / JSON report writers."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from repolens.disclaimer import disclaimer_markdown_lines
from repolens.report_metrics import (
    _render_audit_ledger,
    _render_metrics_section,
    format_collapsed_duplicates,
    suppression_suffix,
)
from repolens.report_sections import (
    _render_change_set_section,
    _render_complexity_section,
    _render_coverage_section,
    _render_durability_gaps_section,
    _render_import_graph_section,
    _render_provenance_section,
    _render_quality_scorecard_section,
    _render_supply_chain_section,
    _render_suppressed_section,
    _render_testing_inventory_section,
    _render_theme_breakdown,
)
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

GATE_ADEQUACY_ONE_LINER = (
    "Gate confidence reflects review-package adequacy "
    '(checklist coverage + open severity penalties), not a "% secure" score.'
)


def report_timestamp(when: datetime | None = None) -> datetime:
    """UTC clock used for report filenames and headings (all formats share this)."""
    if when is None:
        return datetime.now(UTC)
    if when.tzinfo is None:
        return when.replace(tzinfo=UTC)
    return when.astimezone(UTC)


def report_stamp(when: datetime | None = None) -> str:
    """Filesystem-safe UTC stamp: ``YYYY-MM-DD_HHMM`` (avoids same-day overwrites)."""
    return report_timestamp(when).strftime("%Y-%m-%d_%H%M")


def report_heading_time(when: datetime | None = None) -> str:
    """Human-readable UTC time for the report title: ``YYYY-MM-DD HH:MM UTC``."""
    return report_timestamp(when).strftime("%Y-%m-%d %H:%M UTC")


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


def format_two_lane_headline(report: FindingReport) -> str:
    """Punchy SecureVibes-style opener — provenance-honest."""
    prov = report.provenance
    fb = prov.fastBrainFiles if prov else None
    llm = prov.llmPackFiles if prov else None
    s = report.summary
    counts = (
        f"{s.critical} critical · {s.high} high · "
        f"{s.medium} medium · {s.low} low"
    )
    dur = format_duration(report.durationSeconds)
    parts: list[str] = []
    if fb is not None:
        fb_bit = f"Fast Brain: {fb} file(s)"
        if prov and prov.fastBrainSeconds is not None:
            fb_bit += f" in {prov.fastBrainSeconds:.1f}s"
        parts.append(fb_bit)
    if llm is not None:
        if prov and prov.llmBypassed:
            parts.append("Slow Brain: bypassed (triage clean)")
        else:
            sb_bit = f"Slow Brain: {llm} file(s)"
            if prov and prov.llmSeconds is not None:
                sb_bit += f" in {prov.llmSeconds:.1f}s"
            parts.append(sb_bit)
    if dur:
        parts.append(dur)
    parts.append(counts)
    return " · ".join(parts)


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


def _markdown_heading(
    report: FindingReport,
    *,
    mode: str,
    commit_go: str,
    push_go: str,
    when: datetime | None,
) -> list[str]:
    heading_time = report_heading_time(when)
    lines = [
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
            "> [!NOTE]",
            "> **Audit confidence & gate interpretation**",
            f"> {GATE_ADEQUACY_ONE_LINER} "
            "See RepoLens `docs/faq.md` → *What do report metrics mean?*",
        ]
    )
    headline = format_two_lane_headline(report)
    if headline:
        lines.extend(["", f"**Two-Lane:** {headline}", ""])
    return lines


def _llm_status_line(report: FindingReport) -> str | None:
    reused = getattr(report, "llmReusedFrom", None)
    if reused:
        return (
            f"- **LLM:** reused from last successful AI pass "
            f"(`{reused}`) — not a fresh deep review"
        )
    if getattr(report, "llmBypassed", False):
        return "- **LLM:** bypassed (scanners clean at triage floor)"
    if getattr(report, "llmSkipped", False):
        return (
            "- **LLM:** skipped (no fingerprint delta under `--changed` and "
            "no prior LLM snapshot to reuse)"
        )
    return None


def _markdown_verdict(report: FindingReport) -> list[str]:
    lines = [
        "",
        "## Gate verdict",
        "",
        f"- **Gate confidence:** {report.confidence}% "
        "(review-package adequacy — not “% secure”)",
        (
            f"- **Counts:** Critical {report.summary.critical} · "
            f"High {report.summary.high} · Medium {report.summary.medium} · "
            f"Low {report.summary.low}"
            + (
                f" · Suppressed {len(report.suppressedIssues)}"
                f"{suppression_suffix(report)}"
                if report.suppressedIssues
                else ""
            )
        ),
    ]
    collapsed = format_collapsed_duplicates(report)
    if collapsed is not None:
        lines.append(f"- **Critical/High rows:** {collapsed}")
    status = _llm_status_line(report)
    if status is not None:
        lines.append(status)
    repairs = getattr(report, "llmRepairAttempts", None)
    if repairs:
        lines.append(
            f"- **LLM JSON repairs:** {repairs} micro-repair "
            "attempt(s) (hard cap 1 per pass)"
        )
    lines.append("")
    return lines


def _markdown_finding_fields() -> list[str]:
    return [
        "## Finding fields",
        "",
        "- **Priority:** P1 security · P2 bugs/reliability · P3 architecture/quality.",
        "- **Fingerprint:** identity of the issue across runs — **prefer this** for "
        "`repolens explain` and for ignore / `feedback down`.",
        "- **Occurrence:** this appearance in *this* report only (also accepted by "
        "`explain`; changes every run).",
        "- **Source:** `scanner` · `heuristic` (Fast Brain) · `llm`.",
        "- **Location:** verified → SARIF-eligible; unverified → Markdown/JSON only.",
        "",
        "Full glossary: RepoLens `docs/faq.md` → *What do finding fields mean?*",
        "",
    ]


def _markdown_priority_bands(report: FindingReport) -> list[str]:
    lines: list[str] = []
    bands = (
        ("P1", "P1 — Security"),
        ("P2", "P2 — Bugs, reliability, performance"),
        ("P3", "P3 — Architecture & quality"),
    )
    for band, label in bands:
        band_issues = [
            i for i in report.issues if i.priority == band and i.source != "llm"
        ]
        lines.append(f"## {label}")
        lines.append("")
        if not band_issues:
            lines.append("_No findings in this band._")
            lines.append("")
            continue
        for issue in band_issues:
            lines.extend(_render_issue(issue))
            lines.append("")
    return lines


def _markdown_model_notes(report: FindingReport) -> list[str]:
    """Model writing stays visible and does not change the four counts."""
    notes = [issue for issue in report.issues if issue.source == "llm"]
    if not notes:
        return []
    lines = [
        "## Model notes",
        "",
        "The model wrote these. They do not change Critical, High, Medium, or Low.",
        "",
    ]
    for issue in notes:
        lines.append(
            f"- **{issue.title}** (`{issue.file}:{issue.line}`). {issue.explanation}"
        )
    lines.append("")
    return lines


def _markdown_scanners(report: FindingReport) -> list[str]:
    lines = ["## Automated scanners", ""]
    if not report.scannerRuns:
        lines.extend(["_No scanners requested or configured._", ""])
        return lines
    for run in report.scannerRuns:
        detail = f" — {run.detail}" if run.detail else ""
        count = f" ({run.findingCount} finding(s))" if run.status == "ran" else ""
        lines.append(f"- **{run.tool}**: `{run.status}`{detail}{count}")
    lines.append("")
    return lines


def _markdown_plan(report: FindingReport) -> list[str]:
    from repolens.report_sections import plan_to_fix_lines

    return ["## Plan to fix", "", *plan_to_fix_lines(report)]


def _markdown_scores(report: FindingReport) -> list[str]:
    if report.scores is None:
        return []
    score = report.scores
    return [
        "## Architecture scores",
        "",
        "| Dimension | Score (1–10) |",
        "|-----------|--------------|",
        f"| Architecture | {score.architecture} |",
        f"| Security | {score.security} |",
        f"| Maintainability | {score.maintainability} |",
        f"| Performance | {score.performance} |",
        f"| Scalability | {score.scalability} |",
        f"| Production readiness | {score.productionReadiness} |",
        "",
    ]


def render_markdown(
    report: FindingReport,
    *,
    mode: str,
    commit_go: str,
    push_go: str,
    when: datetime | None = None,
) -> str:
    lines = _markdown_heading(
        report, mode=mode, commit_go=commit_go, push_go=push_go, when=when
    )
    lines.extend(_markdown_verdict(report))
    lines.extend(_render_metrics_section(report))
    lines.extend(_markdown_finding_fields())
    lines.extend(_markdown_priority_bands(report))
    lines.extend(_markdown_model_notes(report))
    lines.extend(_markdown_scanners(report))
    lines.extend(_render_quality_scorecard_section(report))
    lines.extend(_render_complexity_section(report))
    lines.extend(_render_testing_inventory_section(report))
    lines.extend(_render_supply_chain_section(report))
    lines.extend(_render_change_set_section(report))
    lines.extend(_render_import_graph_section(report))
    lines.extend(_render_provenance_section(report))
    lines.extend(_render_suppressed_section(report))
    lines.extend(_markdown_plan(report))
    lines.extend(_render_durability_gaps_section(report))
    lines.extend(_render_coverage_section(report))
    lines.extend(_render_theme_breakdown(report))
    lines.extend(_markdown_scores(report))
    lines.extend(_render_audit_ledger(report))
    lines.extend(disclaimer_markdown_lines())
    return "\n".join(lines)


def is_coverage_transport_gap(gap: str) -> bool:
    """True when a gap is a coverage N/A or missed note (not a real durability todo)."""
    return bool(_COVERAGE_TRANSPORT_GAP_RE.match(gap.strip()))




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


def _diff_suffix(issue: Issue) -> str:
    if issue.introducedInDiff is True:
        return " — New / touched in this diff"
    if issue.introducedInDiff is False:
        return " — Pre-existing baseline"
    return ""


def _render_issue(issue: Issue) -> list[str]:
    block = [
        f"### [{issue.severity.value}] {issue.title}{_diff_suffix(issue)}",
        f"- **Priority:** {issue.priority}",
        f"- **File:** `{issue.file}`",
        f"- **Line:** {issue.line}",
        f"- **Category:** {issue.category}",
    ]
    if issue.stableId:
        block.append(
            f"- **Fingerprint:** `{issue.stableId}` "
            "(prefer for `explain` / ignore)"
        )
    if issue.runId:
        block.append(
            f"- **Occurrence:** `{issue.runId}` "
            "(this report only; also works with `explain`)"
        )
    if issue.source:
        block.append(f"- **Source:** {issue.source}")
    if issue.locationVerified is False:
        block.append(
            "- **Location:** unverified — omitted from SARIF "
            "(provide a resolvable `anchorQuote` or use scanner evidence)"
        )
    elif issue.locationVerified is True:
        block.append("- **Location:** verified (SARIF-eligible)")
    block.extend(
        [
            f"- **Explanation:** {issue.explanation}",
            f"- **Impact:** {issue.impact or '_n/a_'}",
            f"- **Recommended fix:** {issue.recommendedFix}",
            f"- **Fix timing:** {issue.fixTiming}",
        ]
    )
    if issue.owasp:
        block.append(f"- **OWASP:** {issue.owasp}")
    if issue.cwe:
        block.append(f"- **CWE:** {issue.cwe}")
    if issue.packageName or issue.advisoryId:
        pkg_bits = []
        if issue.packageName:
            pkg_bits.append(f"`{issue.packageName}`")
        if issue.installedVersion:
            pkg_bits.append(f"installed `{issue.installedVersion}`")
        if issue.fixedVersion:
            pkg_bits.append(f"fixed `{issue.fixedVersion}`")
        if issue.advisoryId:
            pkg_bits.append(f"advisory `{issue.advisoryId}`")
        block.append(f"- **SCA (scanner):** {', '.join(pkg_bits)}")
    if issue.usageHint:
        label = {
            "referenced_in_source": "referenced in source",
            "no_reference_found": "no reference found in scanned source",
        }.get(issue.usageHint, issue.usageHint)
        block.append(
            f"- **Usage hint (not reachability):** {label}"
            + (f" — {issue.usageHintDetail}" if issue.usageHintDetail else "")
        )
    if issue.clusteredCount and issue.clusteredCount > 1:
        block.append(
            f"- **Clustered:** {issue.clusteredCount} near-duplicate finding(s) collapsed"
        )
    if issue.codeExample.strip():
        block.append("- **Code example:**")
        block.append("")
        block.extend(render_code_example_fenced(issue.codeExample))
    elif issue.severity in {Severity.CRITICAL, Severity.HIGH}:
        block.append("- **Code example:** _MISSING (invalid for Critical/High)_")
    return block
