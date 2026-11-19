"""The selfdog script reviews the checkout it lives in."""

from __future__ import annotations

import subprocess
from pathlib import Path

from repolens.schema import FindingReport, Issue, Severity, Summary

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "selfdog-review.sh"


def test_selfdog_review_runs_the_full_audit_on_this_checkout() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert 'cd "$(dirname "$0")/.."' in text
    assert 'review_path="${TARGET:-.}"' in text
    assert 'export PYTHONPATH="$PWD/src' in text
    for flag in (
        "--out reports/selfdog-deep",
        "--full",
        "--full-audit",
        "--deep",
        "--scanners gitleaks,semgrep,osv,trivy,checkov",
        "--model qwen2.5-coder:32b",
        "--timeout 7200",
        "--verbose",
        "--report-html",
        "--git-diff auto",
        "--format both",
        "--scanners-only",
    ):
        assert flag in text
    assert "PatternSorcerer" not in text
    assert '"$@"' in text
    assert "Often an hour or more" in text
    assert "--dry-run" in text


def test_selfdog_with_no_arguments_opens_the_menu() -> None:
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    text = result.stdout
    assert "1  full" in text
    assert "Often an hour or more" in text
    assert "--full --full-audit --deep" in text
    assert "2  html" in text
    assert "--report-html" in text
    assert "3  changed" in text
    assert "--git-diff auto" in text
    assert "4  short" in text
    assert "--format both" in text
    assert "5  fast" in text
    assert "--scanners-only" in text
    assert "Choice [1-5]" in text
    assert "Usage: repolens review" not in result.stderr


def test_selfdog_html_writes_one_page_for_the_named_report(tmp_path: Path) -> None:
    report = FindingReport(
        confidence=80,
        summary=Summary(high=1),
        issues=[
            Issue(
                severity=Severity.HIGH,
                priority="P1",
                category="demo",
                file="src/app.py",
                line=4,
                title="Secret in a log line",
                explanation="The log line includes a secret",
                impact="The secret can leak",
                recommendedFix="Remove the secret",
                codeExample="print(1)\n",
                source="scanner",
            )
        ],
    )
    stem = tmp_path / "gate_review_report_review_2026-11-19_1700"
    json_path = stem.with_suffix(".json")
    json_path.write_text(report.model_dump_json(), encoding="utf-8")
    stem.with_suffix(".md").write_text("# Gate review\n", encoding="utf-8")

    result = subprocess.run(
        [str(SCRIPT), "html", str(json_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    page = stem.with_suffix(".html").read_text(encoding="utf-8")
    assert "Secret in a log line" in page
    assert "<style>" in page


def test_selfdog_unknown_choice_exits_2() -> None:
    result = subprocess.run(
        [str(SCRIPT), "nope"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "full" in result.stdout + result.stderr
