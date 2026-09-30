"""Markdown section renderers for gate reports.

Imported by ``repolens.report``. These functions may import ``repolens.report``
lazily so the package import does not cycle.
"""

from __future__ import annotations

import re

from repolens.coverage import (
    checklist_title,
    explain_answered,
    explain_missed_id,
    parse_coverage_notes,
)
from repolens.schema import FindingReport, Issue, QualityScorecard, ThemeEntry

_STATUS_LABEL = {
    "covered": "Answered",
    "na": "Does not apply",
    "missed": "Not answered",
}


def _render_quality_scorecard_section(report: FindingReport) -> list[str]:
    q: QualityScorecard | None = report.quality
    if q is None:
        return []
    lines: list[str] = [
        "## Quality scorecard (Fast Brain)",
        "",
        "| Signal | Count |",
        "|--------|------:|",
        f"| Mega-files | {q.megaFileCount} |",
        f"| Deep nesting | {q.deepNestingCount} |",
        f"| Near-clone clusters | {q.nearCloneClusters} |",
        f"| Near-clone occurrences | {q.nearCloneOccurrences} |",
        f"| Near-clone findings emitted | {q.nearCloneFindingsEmitted} |",
        f"| Files scanned | {q.filesScanned} |",
        "",
        "| Signal | Principle lens |",
        "|--------|----------------|",
        "| Near-clone clusters | DRY |",
        "| Mega-files | KISS / SRP proxy |",
        "| Deep nesting | KISS |",
        "",
        "_Import-cycle cyclicity (DIP / layering) is reported under **Import graph**, "
        "not this scorecard._",
        "",
    ]
    for note in q.notes:
        lines.append(f"_{note}._")
        lines.append("")
    lines.append(
        "_Deterministic DRY/KISS signals — not a SOLID/DRY/KISS certification._"
    )
    lines.append("")
    return lines


def _render_complexity_section(report: FindingReport) -> list[str]:
    """Fast Brain cyclomatic + cognitive — Top-10 table (LLM detail is separate)."""
    block = report.complexity
    if block is None:
        return []
    lines: list[str] = [
        "## Complexity (Fast Brain)",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| Functions analysed | {block.functionsAnalysed} |",
        f"| Issues (above threshold) | {block.issueCount} |",
        f"| Max cyclomatic | {block.maxCyclomatic} |",
        f"| Max cognitive | {block.maxCognitive} |",
        f"| P95 cyclomatic | {block.p95Cyclomatic} |",
        f"| P95 cognitive | {block.p95Cognitive} |",
        "",
    ]
    if block.hotspots:
        lines.extend(
            [
                "### Top complexity hotspots",
                "",
                "| File | Function | Line | Cyclomatic | Cognitive |",
                "|------|----------|-----:|----------:|----------:|",
            ]
        )
        for h in block.hotspots:
            lines.append(
                f"| `{h.file}` | `{h.function}` | {h.line} | "
                f"{h.cyclomatic} | {h.cognitive} |"
            )
        lines.append("")
    for note in block.notes:
        lines.append(f"_{note}._")
        lines.append("")
    lines.append(
        "_Deterministic McCabe + cognitive complexity — not a Sonar server "
        "or architecture certification. LLM refactor detail is capped separately "
        "(default top 5)._"
    )
    lines.append("")
    return lines


def _render_testing_inventory_section(report: FindingReport) -> list[str]:
    block = report.testing
    if block is None:
        return []
    lines: list[str] = [
        "## Testing inventory (Fast Brain)",
        "",
        "| Signal | Value |",
        "|--------|------:|",
        f"| Test files | {block.testFileCount} |",
        f"| Test cases | {block.testCaseCount} |",
        f"| Production functions | {block.productionFunctionCount} |",
        f"| Ratio (tests/production function) | {block.testsPerProductionFunction} |",
        "",
        "_Counts test **functions/cases** (Python `ast`), not file-only ratios. "
        "Line coverage is imported separately (v1); scenario adequacy ≠ coverage %._",
        "",
    ]
    for note in block.notes:
        lines.append(f"_{note}._")
        lines.append("")
    return lines


def _render_supply_chain_section(report: FindingReport) -> list[str]:
    """Phase 6.2 SBOM / license inventory (scanner-owned)."""
    sc = report.supplyChain
    if sc is None:
        return []
    lines: list[str] = ["## Supply chain", ""]
    if sc.sbomPath:
        fmt = f" ({sc.sbomFormat})" if sc.sbomFormat else ""
        lines.append(f"- **SBOM**{fmt}: `{sc.sbomPath}`")
    if sc.licenses:
        preview = ", ".join(sc.licenses[:40])
        more = f" (+{len(sc.licenses) - 40} more)" if len(sc.licenses) > 40 else ""
        lines.append(f"- **Licenses observed**: {preview}{more}")
    for note in sc.notes:
        lines.append(f"- {note}")
    if len(lines) == 2:
        lines.append("_No SBOM or license summary produced._")
    lines.append("")
    return lines


def _render_change_set_section(report: FindingReport) -> list[str]:
    """#16: Slow Brain git change-set scope."""
    block = getattr(report, "changeSet", None)
    if block is None:
        return []
    lines: list[str] = [
        "## Change-set scope",
        "",
        (
            f"- **Base:** `{block.base}`"
            if block.base
            else "- **Base:** _(worktree / auto — no merge-base resolved)_"
        ),
        f"- **Git paths:** {block.pathCount}",
        f"- **Note:** {block.note}",
        "",
    ]
    if block.paths:
        lines.append("Paths (capped list):")
        lines.append("")
        for p in block.paths:
            lines.append(f"- `{p}`")
        if block.pathCount > len(block.paths):
            lines.append(
                f"- _…and {block.pathCount - len(block.paths)} more_"
            )
        lines.append("")
    return lines


def _render_import_graph_section(report: FindingReport) -> list[str]:
    """G1: deterministic Python import graph metrics (grimp)."""
    block = report.graph
    if block is None:
        return []
    lines: list[str] = [
        "## Import graph",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| Status | {block.status} |",
        f"| Packages | {block.packageCount} |",
        f"| Modules | {block.moduleCount} |",
        f"| Cycle groups | {block.cycleCount} |",
        f"| Cyclicity | {block.cyclicity} |",
        "",
        "_Deterministic Python import cycles (grimp) — DIP / module-boundary "
        "layering signal, not an architecture certification._",
        "",
    ]
    return lines


def _provenance_identity_lines(prov) -> list[str]:
    lines: list[str] = []
    if prov.repoLensVersion:
        lines.append(f"- **RepoLens**: `{prov.repoLensVersion}`")
    if prov.gitSha:
        lines.append(f"- **Git SHA**: `{prov.gitSha}`")
    if prov.provider or prov.model:
        lines.append(f"- **Model**: `{prov.provider or 'n/a'}` / `{prov.model or 'n/a'}`")
    if prov.scannerTools:
        lines.append(f"- **Scanners**: {', '.join(prov.scannerTools)}")
    return lines


def _provenance_triage_lines(prov) -> list[str]:
    lines = [
        f"- **Triage routing**: {'on' if prov.triageRouting else 'off'}",
        (
            f"- **LLM bypassed**: {'yes' if prov.llmBypassed else 'no'}"
            + (f" (hits: {prov.triageHits})" if prov.triageRouting else "")
        ),
    ]
    if prov.failOnScannerOnly:
        lines.append("- **Fail-on gate**: scanner findings only")
    lines.extend(f"- {note}" for note in prov.notes)
    return lines


def _render_provenance_section(report: FindingReport) -> list[str]:
    """Phase 6.3 CI provenance / triage outcome."""
    prov = report.provenance
    if prov is None and not report.llmBypassed and report.triageHits is None:
        return []
    lines: list[str] = ["## Provenance", ""]
    if prov is not None:
        lines.extend(_provenance_identity_lines(prov))
        lines.extend(_provenance_triage_lines(prov))
    else:
        lines.append(f"- **LLM bypassed**: {'yes' if report.llmBypassed else 'no'}")
    lines.append("")
    return lines


def _render_suppressed_section(report: FindingReport) -> list[str]:
    """Phase 6.7: audit list of findings excluded from gates/SARIF."""
    rows = report.suppressedIssues
    if not rows:
        return []
    lines: list[str] = [
        "## Suppressed",
        "",
        "_Excluded from fail-on and SARIF; kept here for audit._",
        "",
    ]
    from repolens.report import _diff_suffix

    for row in rows:
        issue = row.issue
        sid = f" `{issue.stableId}`" if issue.stableId else ""
        note = f" — {row.note}" if row.note else ""
        lines.append(
            f"- **{issue.title}**{_diff_suffix(issue)} (`{issue.file}:{issue.line}`){sid} — "
            f"{row.mechanism} / `{row.reason}`{note}"
        )
    lines.append("")
    return lines



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
