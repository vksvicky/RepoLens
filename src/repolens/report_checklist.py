"""Checklist, plan-to-fix, and theme breakdown Markdown sections."""

from __future__ import annotations

import re

from repolens.coverage import (
    checklist_title,
    explain_answered,
    explain_missed_id,
    parse_coverage_notes,
)
from repolens.schema import FindingReport, Issue, ThemeEntry

_STATUS_LABEL = {
    "covered": "Answered",
    "na": "Does not apply",
    "missed": "Not answered",
}


def _render_durability_gaps_section(report: FindingReport) -> list[str]:
    """Render actionable durability gaps as checkboxes; omit coverage transport notes."""
    from repolens.report import is_coverage_transport_gap
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
        "## Checklist",
        "",
        (
            "These questions check security, reliability, and architecture. "
            "An answered question points at a finding: apply its recommended fix. "
            "A question that does not apply is closed by a fact from this repository. "
            "A question that was not answered is unfinished review work: follow the "
            "step on that question. One unanswered question lowers its band by 4 points."
        ),
        "",
        (
            f"- **Answered:** {len(covered)} · **Does not apply:** {len(na)} · "
            f"**Not answered:** {len(missed)}"
        ),
        "",
    ]
    if missed:
        lines.append("### Not answered")
        lines.append("")
        stored = dict(cov.missedNotes) if cov is not None else {}
        for cid in missed:
            sentence = stored.get(cid) or explain_missed_id(cid, report.durabilityGaps)
            lines.append(f"- {sentence}")
        lines.append("")
    if covered:
        lines.append("### Answered")
        lines.append("")
        for cid in covered:
            lines.append(f"- {explain_answered(cid, report.issues)}")
        lines.append("")
    if na:
        floored = any(
            gap.startswith("metrics.vacuous_pass_confidence_floored:")
            for gap in report.durabilityGaps
        )
        if floored:
            lines.append("### Model said these do not apply")
            lines.append("")
            lines.append(
                "The confidence floor did not accept these lines as facts "
                "from the repository."
            )
            lines.append("")
        else:
            lines.append("### Does not apply")
            lines.append("")
        for cid, reason in na.items():
            title = checklist_title(cid)
            label = cid if title == cid else f"{title} ({cid})"
            lines.append(f"- {label}. {reason}")
        lines.append("")
    return lines


def _package_named(package: str, blob: str) -> bool:
    """True when *package* appears as its own name, not as a prefix of a longer one."""
    if len(package) < 4:
        return False
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(package)}(?![A-Za-z0-9_-])"
    return re.search(pattern, blob, flags=re.IGNORECASE) is not None


def _echoes_suppressed(issue: Issue, report: FindingReport) -> bool:
    """True when an active row restates an advisory the team already suppressed."""
    blob = " ".join(
        part
        for part in (
            issue.title,
            issue.explanation,
            issue.file,
            issue.packageName or "",
            issue.advisoryId or "",
        )
        if part
    ).lower()
    for row in report.suppressedIssues:
        other = row.issue
        if (
            issue.advisoryId
            and other.advisoryId
            and issue.advisoryId.strip().upper() == other.advisoryId.strip().upper()
        ):
            return True
        advisory = (other.advisoryId or "").strip()
        if len(advisory) >= 6 and advisory.lower() in blob:
            return True
        package = (other.packageName or "").strip()
        if _package_named(package, blob):
            return True
    return False


def plan_to_fix_lines(report: FindingReport) -> list[str]:
    from repolens.complexity.thresholds import COGNITIVE_MEDIUM_MAX, CYCLO_MEDIUM_MAX
    from repolens.plan_tiers import render_plan_tiers

    immediate = [
        issue
        for issue in report.issues
        if issue.fixTiming == "immediately" and not _echoes_suppressed(issue, report)
    ]
    block = report.complexity
    hot = []
    if block is not None:
        hot = [
            row
            for row in block.hotspots
            if row.cyclomatic > CYCLO_MEDIUM_MAX or row.cognitive > COGNITIVE_MEDIUM_MAX
        ]
    return render_plan_tiers(immediate, hot)


def _checklist_status(theme: ThemeEntry) -> str:
    return _STATUS_LABEL.get(theme.status, theme.status)


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
                f"| {t.title} | {_checklist_status(t)} | {t.findingCount} | {notes} |"
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
