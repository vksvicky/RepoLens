"""Two visual blocks: the deterministic gate versus the AI deep audit.

Shared by the Markdown report and the CLI summary so both read the same way.
The gate depends only on scanners and Fast Brain; the AI audit is a separate
signal and is never blended into the gate verdict.
"""

from __future__ import annotations

from repolens.schema import FindingReport

_BANDS = (
    ("Security", "securityAuditConfidence", "p1"),
    ("Reliability", "reliabilityAuditConfidence", "p2"),
    ("Architecture", "architectureAuditConfidence", "p3"),
)


def deterministic_gate_passes(report: FindingReport) -> bool:
    """True when no Critical or High finding is open.

    Scanner failed status alone does not flip FAIL.
    """
    return report.summary.critical + report.summary.high == 0


def _scanner_ratio(report: FindingReport) -> str | None:
    runs = report.scannerRuns
    if not runs:
        return None
    ran = sum(1 for run in runs if run.status == "ran")
    return f"Scanners: {ran}/{len(runs)}"


def deterministic_gate_lines(report: FindingReport) -> list[str]:
    """Heading plus one detail line for the scanner and Fast Brain gate."""
    verdict = "PASS" if deterministic_gate_passes(report) else "FAIL"
    high_count = report.summary.critical + report.summary.high
    parts: list[str] = []
    ratio = _scanner_ratio(report)
    if ratio is not None:
        parts.append(ratio)
    parts.append(f"Fast Brain Critical/High {high_count}")
    return [f"DETERMINISTIC GATE: {verdict}", "  " + " · ".join(parts)]


def _band_label(report: FindingReport, name: str, attr: str) -> str:
    value = getattr(report, attr)
    if value is not None:
        return f"{name} {value}%"
    if report.auditIncomplete:
        return f"{name} UNVERIFIED"
    return f"{name} not run"


def _headline_value(report: FindingReport) -> str:
    if report.auditIncomplete:
        return "INCOMPLETE"
    scored = [
        getattr(report, attr)
        for _, attr, _ in _BANDS
        if getattr(report, attr) is not None
    ]
    if not scored:
        return "NOT RUN"
    return f"{min(scored)}%"


def ai_audit_lines(report: FindingReport) -> list[str]:
    """Heading plus per-band detail; INCOMPLETE and UNVERIFIED when incomplete."""
    labels = [_band_label(report, name, attr) for name, attr, _ in _BANDS]
    return [f"AI DEEP AUDIT: {_headline_value(report)}", "  " + " · ".join(labels)]


def markdown_blocks(report: FindingReport) -> list[str]:
    """Markdown lines placed before the metrics glossary."""
    gate = deterministic_gate_lines(report)
    ai = ai_audit_lines(report)
    return [
        "## Gate and AI audit",
        "",
        f"**{gate[0]}**",
        "",
        f"- {gate[1].strip()}",
        "",
        f"**{ai[0]}**",
        "",
        f"- {ai[1].strip()}",
        "",
        "_The gate uses scanners and Fast Brain only. The AI audit is scored "
        "separately and never changes the gate verdict._",
        "",
    ]
