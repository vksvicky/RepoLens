"""Board-ready 2-page executive summary (#106)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from repolens.cli import app
from repolens.executive_summary import render_executive_summary_html, render_executive_summary_md
from repolens.schema import (
    FindingReport,
    GraphBlock,
    Issue,
    ProvenanceBlock,
    Severity,
    Summary,
)

runner = CliRunner()


def _report() -> FindingReport:
    return FindingReport(
        confidence=78,
        summary=Summary(critical=0, high=1, medium=0, low=1),
        securityAuditConfidence=78,
        reliabilityAuditConfidence=95,
        architectureAuditConfidence=88,
        provenance=ProvenanceBlock(
            repoLensVersion="0.1.1",
            gitSha="deadbeef",
            provider="openai",
            model="gpt-4.1-mini",
            dirtyTree=False,
            journalTipHash="tip",
            promptTemplateHash="tmpl",
        ),
        graph=GraphBlock(status="ok", cyclicity=4, cycleCount=1, moduleCount=10),
        issues=[
            Issue(
                severity=Severity.HIGH,
                priority="P1",
                category="sec.authn_authz",
                file="src/webhooks.py",
                line=88,
                title="Webhook HMAC uses ==",
                explanation="Timing-leak risk on signature compare.",
                impact="Forged webhooks can mark invoices paid.",
                recommendedFix="Use hmac.compare_digest.",
                codeExample="hmac.compare_digest(a, b)",
            ),
        ],
    )


def test_executive_md_has_two_pages_and_honesty() -> None:
    text = render_executive_summary_md(_report())
    assert "Page 1" in text or "## Page 1" in text
    assert "Page 2" in text or "## Page 2" in text
    assert "not" in text.lower() and "% secure" in text.lower()
    assert "Security" in text and "Reliability" in text and "Architecture" in text
    assert "Webhook HMAC" in text
    assert "person-week" in text.lower() or "order-of-magnitude" in text.lower()
    assert "deadbeef" in text or "Attestation" in text


def test_executive_html_traffic_lights() -> None:
    html = render_executive_summary_html(_report())
    assert "traffic" in html.lower() or "●" in html or "light" in html.lower()
    assert "78" in html
    assert "gate" in html.lower()


def test_cli_export_executive_summary(tmp_path: Path) -> None:
    report = _report()
    json_path = tmp_path / "gate_review_report_review_2026-10-09_1200.json"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (tmp_path / json_path.stem).with_suffix(".md").write_text("# x\n", encoding="utf-8")
    # sibling md for export arg flexibility
    md = tmp_path / f"{json_path.stem}.md"
    md.write_text("# Gate\n", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "export", str(md), "--executive-summary",
            "--out", str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 0, result.output
    outs = list((tmp_path / "out").glob("executive_summary_*"))
    assert outs, result.output
    body = outs[0].read_text(encoding="utf-8")
    assert "Page" in body
