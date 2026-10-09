"""Deterministic gate vs AI deep audit blocks (Markdown + CLI summary)."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from rich.console import Console

from repolens.report import render_markdown
from repolens.report_blocks import (
    ai_audit_lines,
    deterministic_gate_lines,
    deterministic_gate_passes,
)
from repolens.schema import FindingReport, ScannerRun, Summary


def _scanner(tool: str, status: str) -> ScannerRun:
    return ScannerRun(tool=tool, status=status)


def _report(**overrides: object) -> FindingReport:
    base: dict[str, object] = {
        "confidence": 80,
        "summary": Summary(),
        "securityAuditConfidence": 85,
        "reliabilityAuditConfidence": 80,
        "architectureAuditConfidence": 75,
        "scannerRuns": [_scanner("semgrep", "ran"), _scanner("trivy", "skipped")],
    }
    base.update(overrides)
    return FindingReport(**base)  # type: ignore[arg-type]


def _md(report: FindingReport) -> str:
    return render_markdown(report, mode="review", commit_go="go", push_go="go")


def _cli(report: FindingReport) -> str:
    from repolens.cli import export as export_mod

    buf = StringIO()
    fake = Console(file=buf, force_terminal=False, width=140)
    with patch.object(export_mod, "console", fake):
        export_mod._print_summary(report.confidence, 5, report, dry_run=False)
    return buf.getvalue()


# --- Right ---------------------------------------------------------------


def test_markdown_contains_both_blocks_in_order() -> None:
    md = _md(_report())
    assert "DETERMINISTIC GATE: PASS" in md
    assert "AI DEEP AUDIT: 75%" in md
    assert md.index("DETERMINISTIC GATE") < md.index("AI DEEP AUDIT")
    assert md.index("AI DEEP AUDIT") < md.index("## Metrics")


def test_markdown_gate_fails_on_high_findings() -> None:
    md = _md(_report(summary=Summary(critical=0, high=2)))
    assert "DETERMINISTIC GATE: FAIL" in md
    assert "Critical/High 2" in md


def test_scanner_ratio_counts_only_ran() -> None:
    lines = deterministic_gate_lines(_report())
    assert "Scanners: 1/2" in lines[1]


def test_ai_block_lists_each_band() -> None:
    text = "\n".join(ai_audit_lines(_report()))
    assert "Security 85%" in text
    assert "Reliability 80%" in text
    assert "Architecture 75%" in text


# --- Boundary / edge -----------------------------------------------------


def test_gate_passes_at_zero_critical_high_only() -> None:
    assert deterministic_gate_passes(_report(summary=Summary(medium=9, low=9)))
    assert not deterministic_gate_passes(_report(summary=Summary(critical=1)))
    assert not deterministic_gate_passes(_report(summary=Summary(high=1)))


def test_no_scanner_runs_omits_ratio() -> None:
    lines = deterministic_gate_lines(_report(scannerRuns=[]))
    assert "Scanners" not in lines[1]
    assert "Fast Brain Critical/High 0" in lines[1]


def test_no_ai_bands_reports_not_run_not_zero() -> None:
    report = _report(
        securityAuditConfidence=None,
        reliabilityAuditConfidence=None,
        architectureAuditConfidence=None,
    )
    lines = ai_audit_lines(report)
    assert lines[0] == "AI DEEP AUDIT: NOT RUN"
    assert "0%" not in "\n".join(lines)


def test_sentinel_only_security_band_marks_others_not_run() -> None:
    report = _report(reliabilityAuditConfidence=None, architectureAuditConfidence=None)
    text = "\n".join(ai_audit_lines(report))
    assert "AI DEEP AUDIT: 85%" in text
    assert "Architecture not run" in text
    assert "UNVERIFIED" not in text


# --- Inverse / error: incomplete audit -----------------------------------


def test_incomplete_audit_says_incomplete_and_unverified() -> None:
    report = _report(
        auditIncomplete=True,
        architectureAuditConfidence=None,
        durabilityGaps=["pass_degraded:p3:parse_failed"],
    )
    lines = ai_audit_lines(report)
    assert lines[0] == "AI DEEP AUDIT: INCOMPLETE"
    assert "Architecture UNVERIFIED" in lines[1]
    assert "Security 85%" in lines[1]


def test_incomplete_without_gap_detail_flags_missing_bands_unverified() -> None:
    report = _report(auditIncomplete=True, reliabilityAuditConfidence=None)
    lines = ai_audit_lines(report)
    assert lines[0] == "AI DEEP AUDIT: INCOMPLETE"
    assert "Reliability UNVERIFIED" in lines[1]


def test_markdown_incomplete_flows_through() -> None:
    md = _md(_report(auditIncomplete=True, architectureAuditConfidence=None))
    assert "AI DEEP AUDIT: INCOMPLETE" in md
    assert "Architecture UNVERIFIED" in md


def test_deterministic_gate_unaffected_by_incomplete_ai() -> None:
    clean = _report()
    broken = _report(auditIncomplete=True, architectureAuditConfidence=None)
    assert deterministic_gate_lines(clean) == deterministic_gate_lines(broken)


# --- Cross-check: CLI matches Markdown ------------------------------------


def test_cli_summary_prints_both_blocks() -> None:
    out = _cli(_report())
    assert "DETERMINISTIC GATE: PASS" in out
    assert "AI DEEP AUDIT: 75%" in out
    assert "Scanners: 1/2" in out


def test_cli_summary_incomplete() -> None:
    out = _cli(_report(auditIncomplete=True, architectureAuditConfidence=None))
    assert "AI DEEP AUDIT: INCOMPLETE" in out
    assert "Architecture UNVERIFIED" in out


def test_cli_and_markdown_use_same_headings() -> None:
    report = _report(summary=Summary(high=1))
    md, out = _md(report), _cli(report)
    for heading in ("DETERMINISTIC GATE: FAIL", "AI DEEP AUDIT: 75%"):
        assert heading in md
        assert heading in out


# --- Performance ----------------------------------------------------------


def test_block_helpers_are_cheap_on_large_scanner_lists() -> None:
    runs = [_scanner(f"t{i}", "ran") for i in range(5000)]
    report = _report(scannerRuns=runs)
    assert "Scanners: 5000/5000" in deterministic_gate_lines(report)[1]
