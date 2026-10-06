"""Markdown section renderers for gate reports.

Imported by ``repolens.report``. These functions may import ``repolens.report``
lazily so the package import does not cycle.
"""

from __future__ import annotations

from repolens.schema import FindingReport, Issue, QualityScorecard


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
    if prov.dirtyTree is not None:
        lines.append(f"- **Dirty tree**: {'yes' if prov.dirtyTree else 'no'}")
    if prov.provider or prov.model:
        lines.append(f"- **Model**: `{prov.provider or 'n/a'}` / `{prov.model or 'n/a'}`")
    if prov.scannerTools:
        lines.append(f"- **Scanners**: {', '.join(prov.scannerTools)}")
    if prov.scannerDigests:
        digest = ", ".join(f"{k}={v}" for k, v in sorted(prov.scannerDigests.items()))
        lines.append(f"- **Scanner digests**: `{digest}`")
    if prov.promptTemplateHash:
        lines.append(f"- **Prompt template**: `{prov.promptTemplateHash}`")
    if prov.journalTipHash:
        lines.append(f"- **Journal tip**: `{prov.journalTipHash}`")
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


def _render_verification_section(report: FindingReport) -> list[str]:
    """Grounded vs Suspect Critical/High findings after verify_findings."""
    from repolens.schema import Severity

    grounded = [
        i
        for i in report.issues
        if i.verificationStatus == "grounded"
        and i.severity in {Severity.CRITICAL, Severity.HIGH}
    ]
    suspect = [
        i
        for i in report.issues
        if i.verificationStatus == "suspect"
        and i.severity in {Severity.CRITICAL, Severity.HIGH}
    ]
    if not grounded and not suspect:
        return []
    lines: list[str] = ["## Verification", ""]
    if grounded:
        lines.append("### Grounded")
        lines.append("")
        for issue in grounded:
            lines.append(f"- **{issue.title}** (`{issue.file}:{issue.line}`)")
        lines.append("")
    if suspect:
        lines.append("### Suspect / Unverified")
        lines.append("")
        lines.append(
            "_These Critical/High rows lowered gate confidence; re-check before shipping._"
        )
        lines.append("")
        for issue in suspect:
            lines.append(f"- **{issue.title}** (`{issue.file}:{issue.line}`)")
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
