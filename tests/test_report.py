"""Markdown report writer."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from repolens.report import (
    format_duration,
    is_coverage_transport_gap,
    render_code_example_fenced,
    report_heading_time,
    report_stamp,
    write_json_report,
    write_markdown_report,
)
from repolens.schema import (
    CoverageBlock,
    FindingReport,
    Issue,
    ScannerRun,
    Severity,
    Summary,
)


def test_report_stamp_includes_date_and_time() -> None:
    when = datetime(2026, 8, 5, 14, 30, 45, tzinfo=ZoneInfo("UTC"))
    assert report_stamp(when) == "2026-08-05_1430"
    assert report_heading_time(when) == "2026-08-05 14:30"


def test_format_duration() -> None:
    assert format_duration(None) is None
    assert format_duration(45) == "45s"
    assert format_duration(1094) == "18m 14s (1094s)"
    assert format_duration(3661) == "1h 1m 1s (3661s)"


def test_write_reports_do_not_overwrite_same_day(tmp_path: Path) -> None:
    report = FindingReport(
        confidence=50,
        summary=Summary(),
        issues=[],
    )
    t1 = datetime(2026, 8, 5, 9, 0, 0, tzinfo=ZoneInfo("UTC"))
    t2 = datetime(2026, 8, 5, 15, 45, 12, tzinfo=ZoneInfo("UTC"))
    md1 = write_markdown_report(report, tmp_path, mode="review", when=t1)
    md2 = write_markdown_report(report, tmp_path, mode="review", when=t2)
    js1 = write_json_report(report, tmp_path, when=t1)
    js2 = write_json_report(report, tmp_path, when=t2)
    assert md1 != md2
    assert js1 != js2
    assert md1.name == "gate_review_report_review_2026-08-05_0900.md"
    assert md2.name == "gate_review_report_review_2026-08-05_1545.md"
    assert js1.name == "gate_review_report_review_2026-08-05_0900.json"
    assert "2026-08-05 09:00" in md1.read_text(encoding="utf-8")
    assert "2026-08-05 15:45" in md2.read_text(encoding="utf-8")


def test_sentinel_and_review_reports_use_distinct_filenames(tmp_path: Path) -> None:
    report = FindingReport(confidence=50, summary=Summary(), issues=[])
    when = datetime(2026, 8, 5, 10, 15, tzinfo=ZoneInfo("UTC"))
    md_sent = write_markdown_report(report, tmp_path, mode="sentinel", when=when)
    md_rev = write_markdown_report(report, tmp_path, mode="review", when=when)
    assert md_sent.name == "gate_review_report_sentinel_2026-08-05_1015.md"
    assert md_rev.name == "gate_review_report_review_2026-08-05_1015.md"
    assert md_sent != md_rev


def test_write_markdown_report_includes_sections(tmp_path: Path) -> None:
    report = FindingReport(
        schemaVersion="1.0",
        confidence=70,
        summary=Summary(critical=0, high=1, medium=0, low=0),
        issues=[
            Issue(
                severity=Severity.HIGH,
                priority="P1",
                category="Secrets",
                file="app.py",
                line=3,
                title="Hardcoded API key",
                explanation="Key embedded in source.",
                impact="Credential theft.",
                recommendedFix="Move to environment variable.",
                codeExample='key = os.environ["API_KEY"]',
                fixTiming="immediately",
            )
        ],
        durabilityGaps=["ci"],
        scannerRuns=[ScannerRun(tool="gitleaks", status="ran", findingCount=1)],
        durationSeconds=1094,
    )
    path = write_markdown_report(report, tmp_path, mode="sentinel")
    text = path.read_text(encoding="utf-8")
    assert path.name.startswith("gate_review_report_sentinel_")
    assert re.match(
        r"gate_review_report_sentinel_\d{4}-\d{2}-\d{2}_\d{4}\.md$", path.name
    )
    assert "**Generated:**" in text
    assert "**Duration:** 18m 14s (1094s)" in text
    assert "## Gate verdict" in text
    assert "Gate confidence:** 70%" in text or "**Gate confidence:** 70%" in text
    assert "Hardcoded API key" in text
    assert "key = os.environ" in text
    assert "## Durability gaps" in text
    assert "## Automated scanners" in text
    assert "gitleaks" in text
    assert "## About" in text
    assert "CycleRunCode Club" in text
    assert "https://cycleruncode.club" in text
    assert "## Disclaimer" in text
    assert "artificial intelligence" in text.lower() or "AI" in text
    assert "as is" in text.lower() or "AS IS" in text
    assert "solely responsible" in text.lower() or "your own risk" in text.lower()
    assert text.index("## About") < text.index("## Disclaimer")


def test_markdown_notes_llm_skipped_but_keeps_counts(tmp_path: Path) -> None:
    report = FindingReport(
        confidence=55,
        summary=Summary(),
        issues=[],
        llmSkipped=True,
        durabilityGaps=["LLM skipped: no delta"],
    )
    text = write_markdown_report(report, tmp_path, mode="review").read_text(
        encoding="utf-8"
    )
    assert "Critical 0" in text
    assert "**LLM:** skipped" in text


def test_markdown_notes_llm_reused(tmp_path: Path) -> None:
    report = FindingReport(
        confidence=75,
        summary=Summary(medium=1),
        issues=[],
        llmSkipped=True,
        llmReusedFrom="2026-08-05T12:00:00+00:00 · qwen:32b",
    )
    text = write_markdown_report(report, tmp_path, mode="review").read_text(
        encoding="utf-8"
    )
    assert "**LLM:** reused from last successful AI pass" in text
    assert "qwen:32b" in text


def test_durability_gaps_omit_coverage_na_and_missed() -> None:
    assert is_coverage_transport_gap(
        "coverage:sec.xss_csrf: N/A — No web surface"
    )
    assert is_coverage_transport_gap(
        "coverage:arch.testing: missed — neither issue nor N/A"
    )
    assert not is_coverage_transport_gap("ci missing Dependabot")
    assert not is_coverage_transport_gap("llm.schema_invalid:p1")


def test_markdown_durability_section_checkboxes_only_real_gaps(tmp_path: Path) -> None:
    report = FindingReport(
        confidence=40,
        summary=Summary(),
        issues=[],
        durabilityGaps=[
            "coverage:sec.xss_csrf: N/A — No web surface",
            "Add Dependabot / SCA to CI",
            "coverage:arch.testing: missed — neither issue nor N/A",
            "llm.schema_invalid:p2",
        ],
        coverage=CoverageBlock(
            covered=[],
            na={"sec.xss_csrf": "No web surface"},
            missed=["arch.testing"],
        ),
    )
    text = write_markdown_report(report, tmp_path, mode="review").read_text(
        encoding="utf-8"
    )
    assert "## Durability gaps" in text
    assert "- [ ] Add Dependabot / SCA to CI" in text
    assert "- [ ] llm.schema_invalid:p2" in text
    # Coverage transport stays out of the checkbox list
    assert "coverage:sec.xss_csrf" not in text.split("## Coverage")[0]
    assert "coverage:arch.testing: missed" not in text.split("## Coverage")[0]
    # Still visible under Coverage
    assert "## Coverage" in text
    assert "sec.xss_csrf" in text


def test_render_code_example_strips_nested_fences() -> None:
    nested = "```swift\nlet x = 1\n```"
    fenced = render_code_example_fenced(nested)
    text = "\n".join(fenced)
    assert text.count("```") == 2  # one open, one close — not nested
    assert "let x = 1" in text
    assert "```swift\n```swift" not in text


def test_markdown_report_does_not_nest_code_fences(tmp_path: Path) -> None:
    report = FindingReport(
        confidence=50,
        summary=Summary(medium=1),
        issues=[
            Issue(
                severity=Severity.MEDIUM,
                priority="P3",
                category="rel.edge_cases",
                file="a.swift",
                line=1,
                title="Incomplete function",
                explanation="missing brace",
                impact="",
                recommendedFix="add brace",
                codeExample="```swift\nfunc f() {}\n```",
            )
        ],
    )
    text = write_markdown_report(report, tmp_path, mode="review").read_text(
        encoding="utf-8"
    )
    # Outer fence only; language tag may appear once inside or on the fence line.
    assert "```\n```swift" not in text
    assert "```\n```\n" not in text
    assert "func f()" in text
