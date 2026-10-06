"""Opt-in finding verification with Grounded / Suspect status and gate penalty."""

from __future__ import annotations

from pathlib import Path

from repolens.config import DeepConfig
from repolens.schema import FindingReport, Issue, Severity

_TAG = "[verify: location unconfirmed]"
_SYMBOL_TAG = "[verify: symbol unconfirmed]"
_CRIT_PENALTY = 8
_HIGH_PENALTY = 4


def _near_symbol(root: Path, issue: Issue) -> bool:
    """True when a cited-looking token matches a symbol near the reported line."""
    path = root / issue.file
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    from repolens.file_outline import collect_symbols

    symbols = collect_symbols(path, text)
    if not symbols:
        # Regex extractors returned nothing — do not punish unknown languages.
        return True
    hay = f"{issue.title} {issue.explanation} {issue.codeExample}".lower()
    cited = False
    for sym in symbols:
        token = sym.name.lower()
        short = token.split(".")[-1]
        if token in hay or short in hay:
            cited = True
            near = (
                abs(sym.start_line - issue.line) <= 40
                or abs(sym.end_line - issue.line) <= 40
                or (sym.start_line <= issue.line <= sym.end_line)
            )
            if near:
                return True
    # Location is enough when the finding did not name a symbol.
    return not cited


def apply_verify_findings(
    root: Path,
    issues: list[Issue],
    deep: DeepConfig,
) -> list[Issue]:
    """Re-check Critical/High locations + symbol grounding when enabled.

    Failures only annotate the issue; they never raise or abort the report.
    """
    if not deep.verify_findings:
        return issues

    from repolens.sarif import verify_issue_location

    out: list[Issue] = []
    for issue in issues:
        if issue.severity not in {Severity.CRITICAL, Severity.HIGH}:
            out.append(
                issue.model_copy(update={"verificationStatus": issue.verificationStatus or "skipped"})
            )
            continue
        try:
            loc = verify_issue_location(root, issue)
        except Exception:
            loc = None
        location_ok = loc is not None
        symbol_ok = _near_symbol(root, issue) if location_ok else False
        grounded = location_ok and symbol_ok
        explanation = issue.explanation
        if not location_ok and _TAG not in explanation:
            explanation = f"{_TAG} {explanation}"
        elif location_ok and not symbol_ok and _SYMBOL_TAG not in explanation:
            explanation = f"{_SYMBOL_TAG} {explanation}"
        out.append(
            issue.model_copy(
                update={
                    "locationVerified": location_ok,
                    "verificationStatus": "grounded" if grounded else "suspect",
                    "explanation": explanation,
                }
            )
        )
    return out


def apply_unverified_gate_penalty(report: FindingReport) -> FindingReport:
    """Lower gate / band confidence for Suspect Critical/High findings."""
    penalty = 0
    suspects = 0
    for issue in report.issues:
        if issue.verificationStatus != "suspect":
            continue
        if issue.severity == Severity.CRITICAL:
            penalty += _CRIT_PENALTY
            suspects += 1
        elif issue.severity == Severity.HIGH:
            penalty += _HIGH_PENALTY
            suspects += 1
    if penalty <= 0:
        return report
    note = (
        f"metrics.verify_suspect_penalty:{penalty} "
        f"({suspects} unverified Crit/High)"
    )
    if note not in report.durabilityGaps:
        report.durabilityGaps.append(note)

    def _drop(value: int | None) -> int | None:
        if value is None:
            return None
        return max(0, min(100, value - penalty))

    report.confidence = max(0, min(100, int(report.confidence) - penalty))
    report.securityAuditConfidence = _drop(report.securityAuditConfidence)
    report.reliabilityAuditConfidence = _drop(report.reliabilityAuditConfidence)
    report.architectureAuditConfidence = _drop(report.architectureAuditConfidence)
    return report
