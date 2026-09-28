"""Markdown section renderers for gate reports.

Imported by ``repolens.report``. These functions may import ``repolens.report``
lazily so the package import does not cycle.
"""

from __future__ import annotations

from repolens.coverage import explain_missed_id, parse_coverage_notes
from repolens.schema import FindingReport, QualityScorecard


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
    for row in rows:
        issue = row.issue
        sid = f" `{issue.stableId}`" if issue.stableId else ""
        note = f" — {row.note}" if row.note else ""
        lines.append(
            f"- **{issue.title}** (`{issue.file}:{issue.line}`){sid} — "
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


def _render_metrics_section(report: FindingReport) -> list[str]:
    """Glossary + band audit confidences (Phase 5.1) + Two-Lane counts (6.11)."""
    from repolens.report import format_collapsed_duplicates
    has_bands = (
        report.securityAuditConfidence is not None
        or report.architectureAuditConfidence is not None
        or report.reliabilityAuditConfidence is not None
    )
    prov = report.provenance
    has_fast_brain = prov is not None and prov.fastBrainFiles is not None
    if not has_bands and not has_fast_brain:
        return []
    lines = [
        "## Metrics",
        "",
        (
            "**Gate** = adequacy of *this review package* (findings + checklist "
            "coverage + scanners) for a go/no-go style decision — **not** "
            "“% secure” or an architecture grade. Band audits score checklist "
            "honesty per P1/`sec.*`, P2/`rel.*`, P3/`arch.*`. See FAQ: "
            "*What do report metrics mean?*"
        ),
        "",
        "| Metric | Value | Meaning |",
        "|--------|-------|---------|",
        (
            f"| Gate confidence | {report.confidence}% | Lowest band, then a penalty "
            "for each missed checklist id. [Why](#why-a-score-is-low) · "
            "[Checklist](#coverage) |"
        ),
    ]
    if prov is not None and prov.fastBrainFiles is not None:
        lines.append(
            f"| Fast Brain files | {prov.fastBrainFiles} | Inventory used for "
            "whole-tree heuristics (Phase 6.11 Two-Lane) |"
        )
        if prov.llmPackFiles is not None:
            lines.append(
                f"| LLM pack files | {prov.llmPackFiles} | Files sent to the model "
                "(0 if bypassed / scanners-only) |"
            )
        if prov.fastBrainSeconds is not None:
            lines.append(
                f"| Fast Brain seconds | {prov.fastBrainSeconds:.1f}s | Wall time "
                "for whole-tree heuristics |"
            )
        if prov.llmSeconds is not None:
            lines.append(
                f"| Slow Brain seconds | {prov.llmSeconds:.1f}s | Wall time for "
                "LLM / deep analysis |"
            )
    if report.securityAuditConfidence is not None:
        lines.append(
            f"| Security audit confidence | {report.securityAuditConfidence}% | "
            "Security checklist plus Critical/High security findings. "
            "[Why](#why-a-score-is-low) |"
        )
    if report.reliabilityAuditConfidence is not None:
        lines.append(
            f"| Reliability audit confidence | {report.reliabilityAuditConfidence}% | "
            "Reliability checklist plus Critical/High reliability findings. "
            "[Why](#why-a-score-is-low) |"
        )
    if report.architectureAuditConfidence is not None:
        lines.append(
            f"| Architecture audit confidence | {report.architectureAuditConfidence}% | "
            "Architecture checklist plus Critical/High architecture findings. "
            "[Why](#why-a-score-is-low) |"
        )
    collapsed = format_collapsed_duplicates(report)
    if collapsed is not None:
        lines.append(
            f"| Duplicates merged | {collapsed} | Same advisory reported by "
            "more than one scanner or the model, before those rows were combined |"
        )
    lines.append(
        "| Severity counts | (above) | Finding tallies — independent of confidence % |"
    )
    if has_bands:
        lines.extend(
            [
                "| Coverage | (below) | [Checklist](#coverage): covered, N/A, or missed |",
                "",
                "### How these % are calculated",
                "",
                "- **Gate** is the lowest band, then a penalty for missed checklist ids.",
                "- **Security, reliability, and architecture** drop when that band has "
                "a missed checklist id or a Critical/High finding.",
                "- Medium and Low findings do not change these percentages.",
                "- Each missed id is explained under [Coverage](#coverage).",
                "- Full arithmetic: RepoLens `docs/faq.md` → *What do report metrics mean?*",
                "",
            ]
        )
        from repolens.metrics import low_audit_explanations

        reasons = list(report.scoreNotes) or low_audit_explanations(report)
        if reasons:
            lines.extend(
                [
                    "### Why a score is low",
                    "",
                    "Shown when a band or the gate is under 70%. Medium and Low findings "
                    "do not change these percentages. Each missed id is explained "
                    "under [Coverage](#coverage).",
                    "",
                ]
            )
            lines.extend(f"- {reason}" for reason in reasons)
            lines.append("")
    else:
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
        "## Coverage",
        "",
        (
            "Each checklist id is covered by a finding, marked N/A with a concrete fact, "
            "or missed. A missed id lowers the gate. The line that counts is "
            "`coverage:<id>: N/A — <what is actually true in this repo>`."
        ),
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
        stored = dict(cov.missedNotes) if cov is not None else {}
        for cid in missed:
            sentence = stored.get(cid) or explain_missed_id(cid, report.durabilityGaps)
            lines.append(f"- {sentence}")
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
