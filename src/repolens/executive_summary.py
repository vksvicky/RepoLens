"""Board-ready 2-page executive summary (Markdown / HTML)."""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from pathlib import Path

from repolens.schema import FindingReport, Issue, Severity

_CRITICAL_HIGH = {Severity.CRITICAL, Severity.HIGH}


def _light(score: int | None) -> str:
    if score is None:
        return "⚪ n/a"
    if score >= 90:
        return f"🟢 {score}%"
    if score >= 70:
        return f"🟡 {score}%"
    return f"🔴 {score}%"


def _gate_status(report: FindingReport) -> str:
    if report.auditIncomplete:
        return "INCOMPLETE (packaging degraded — not a clean pass)"
    if report.summary.critical or report.summary.high:
        return "FAIL (open Critical/High on scanners / Fast Brain)"
    return "PASS (no open Critical/High on the deterministic gate)"


def _debt_signal(report: FindingReport) -> str:
    parts: list[str] = []
    if report.graph is not None:
        parts.append(
            f"import cyclicity {report.graph.cyclicity} "
            f"({report.graph.cycleCount} cycle group(s))"
        )
    if report.complexity is not None:
        parts.append(
            f"complexity issues {report.complexity.issueCount} "
            f"(max cyclomatic {report.complexity.maxCyclomatic})"
        )
    if report.quality is not None:
        parts.append(
            f"mega-files {report.quality.megaFileCount}, "
            f"near-clone clusters {report.quality.nearCloneClusters}"
        )
    return "; ".join(parts) if parts else "no Fast Brain debt signals recorded"


def _top_risks(report: FindingReport, *, limit: int = 5) -> list[Issue]:
    ranked = [i for i in report.issues if i.severity in _CRITICAL_HIGH]
    order = {Severity.CRITICAL: 0, Severity.HIGH: 1}
    ranked.sort(key=lambda i: (order.get(i.severity, 9), i.priority or "", i.title))
    return ranked[:limit]


def _remediation_band(report: FindingReport) -> str:
    n = report.summary.critical + report.summary.high
    if n == 0:
        return "Low — no Critical/High open (order-of-magnitude; not a quote)"
    if n <= 2:
        return "About 0.5–1 person-week (order-of-magnitude; not a quote)"
    if n <= 5:
        return "About 1–3 person-weeks (order-of-magnitude; not a quote)"
    return "About 3+ person-weeks (order-of-magnitude; not a quote)"


def _attestation(report: FindingReport) -> str:
    prov = report.provenance
    if prov is None:
        return "Attestation: provenance block absent on this report."
    dirty = "dirty tree" if prov.dirtyTree else "clean tree"
    return (
        f"Attestation seal — RepoLens {prov.repoLensVersion or '?'} · "
        f"git {prov.gitSha or 'n/a'} ({dirty}) · "
        f"{prov.provider or '?'}/{prov.model or '?'} · "
        f"template {prov.promptTemplateHash or 'n/a'} · "
        f"journal tip {prov.journalTipHash or 'n/a'}"
    )


def render_executive_summary_md(report: FindingReport) -> str:
    """Two-page Markdown suitable for pandoc → PDF/HTML."""
    risks = _top_risks(report)
    lines = [
        "# RepoLens executive summary",
        "",
        "> Gate confidence is **review-package adequacy**, not a “% secure” score. "
        "Person-week bands below are **order-of-magnitude** planning hints, not quotes.",
        "",
        "## Page 1 — Status",
        "",
        "| Band | Traffic light |",
        "|------|---------------|",
        f"| Security | {_light(report.securityAuditConfidence)} |",
        f"| Reliability | {_light(report.reliabilityAuditConfidence)} |",
        f"| Architecture | {_light(report.architectureAuditConfidence)} |",
        f"| Gate confidence | {_light(report.confidence)} |",
        "",
        f"**Deterministic gate:** {_gate_status(report)}",
        "",
        f"**Debt signal:** {_debt_signal(report)}",
        "",
        f"**Counts:** Critical {report.summary.critical} · High {report.summary.high} · "
        f"Medium {report.summary.medium} · Low {report.summary.low}",
        "",
        "## Page 2 — Business risks & remediation",
        "",
    ]
    if not risks:
        lines.append("_No Critical/High findings in this report._")
        lines.append("")
    else:
        lines.append("### Top Critical/High (plain English)")
        lines.append("")
        for issue in risks:
            impact = (issue.impact or issue.explanation or "").strip()
            lines.append(
                f"- **{issue.severity.value.upper()} — {issue.title}** "
                f"(`{issue.file}:{issue.line}`): {impact}"
            )
        lines.append("")
    lines.extend(
        [
            f"**Remediation burden band:** {_remediation_band(report)}",
            "",
            _attestation(report),
            "",
        ]
    )
    return "\n".join(lines)


def render_executive_summary_html(report: FindingReport) -> str:
    """Compact HTML with traffic-light styling (print → PDF friendly)."""
    md_bits = render_executive_summary_md(report)  # keep honesty copy in sync
    sec = report.securityAuditConfidence
    rel = report.reliabilityAuditConfidence
    arch = report.architectureAuditConfidence
    gate = report.confidence

    def cell(label: str, score: int | None) -> str:
        color = "#888"
        if score is not None:
            color = "#2e7d32" if score >= 90 else "#f9a825" if score >= 70 else "#c62828"
        shown = "n/a" if score is None else f"{score}%"
        return (
            f'<div class="light" style="border-left:8px solid {color};padding:0.5rem 1rem;'
            f'margin:0.4rem 0;background:#fafafa">'
            f"<strong>{escape(label)}</strong> "
            f'<span class="traffic">{escape(shown)}</span></div>'
        )

    risks_html = "".join(
        f"<li><strong>{escape(i.severity.value.upper())} — {escape(i.title)}</strong>: "
        f"{escape((i.impact or i.explanation or '').strip())}</li>"
        for i in _top_risks(report)
    ) or "<li><em>No Critical/High findings.</em></li>"

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>RepoLens executive summary</title>
<style>
body {{ font-family: Georgia, serif; max-width: 48rem; margin: 2rem auto; line-height: 1.45; }}
h1,h2 {{ font-family: system-ui, sans-serif; }}
.page {{ page-break-after: always; margin-bottom: 2rem; }}
.note {{ background: #fff8e1; padding: 0.75rem 1rem; border-left: 4px solid #f9a825; }}
</style></head><body>
<h1>RepoLens executive summary</h1>
<p class="note">Gate confidence is <strong>review-package adequacy</strong>, not a
“% secure” score. Person-week bands are <strong>order-of-magnitude</strong>, not quotes.</p>
<section class="page" id="page-1">
<h2>Page 1 — Status</h2>
{cell("Security", sec)}
{cell("Reliability", rel)}
{cell("Architecture", arch)}
{cell("Gate confidence", gate)}
<p><strong>Deterministic gate:</strong> {escape(_gate_status(report))}</p>
<p><strong>Debt signal:</strong> {escape(_debt_signal(report))}</p>
</section>
<section class="page" id="page-2">
<h2>Page 2 — Business risks &amp; remediation</h2>
<ul>{risks_html}</ul>
<p><strong>Remediation burden band:</strong> {escape(_remediation_band(report))}</p>
<p>{escape(_attestation(report))}</p>
</section>
<!-- source honesty mirror length {len(md_bits)} -->
</body></html>
"""


def write_executive_summary(
    report: FindingReport,
    out_dir: Path,
    *,
    fmt: str = "md",
    when: datetime | None = None,
) -> Path:
    """Write ``executive_summary_<stamp>.md`` or ``.html`` under ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = (when or datetime.now(UTC)).strftime("%Y%m%d_%H%M")
    if fmt == "html":
        path = out_dir / f"executive_summary_{stamp}.html"
        path.write_text(render_executive_summary_html(report), encoding="utf-8")
    else:
        path = out_dir / f"executive_summary_{stamp}.md"
        path.write_text(render_executive_summary_md(report), encoding="utf-8")
    return path
