"""Markdown report writer."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from repolens.report import (
    GATE_ADEQUACY_ONE_LINER,
    format_collapsed_duplicates,
    format_duration,
    format_two_lane_headline,
    is_coverage_transport_gap,
    render_code_example_fenced,
    render_markdown,
    report_heading_time,
    report_stamp,
    write_json_report,
    write_markdown_report,
)
from repolens.report_sections import _render_provenance_section
from repolens.schema import (
    CoverageBlock,
    FindingReport,
    Issue,
    ProvenanceBlock,
    ScannerRun,
    Severity,
    Summary,
)


def test_provenance_section_renders_command_and_expanded_argv() -> None:
    report = FindingReport(
        confidence=70,
        summary=Summary(),
        issues=[],
        provenance=ProvenanceBlock(
            repoLensVersion="0.1.2",
            command="repolens audit --path .",
            expandedArgv=[
                "repolens",
                "review",
                "--path",
                ".",
                "--full",
                "--full-audit",
                "--deep",
                "--timeout",
                "3600",
                "--ratchet",
                "--verify-findings",
            ],
        ),
    )
    text = "\n".join(_render_provenance_section(report))
    assert "- **Command**: `repolens audit --path .`" in text
    assert (
        "- **Expanded argv**: `repolens review --path . --full --full-audit "
        "--deep --timeout 3600 --ratchet --verify-findings`"
    ) in text


def test_report_stamp_includes_date_and_time() -> None:
    when = datetime(2026, 8, 5, 14, 30, 45, tzinfo=ZoneInfo("UTC"))
    assert report_stamp(when) == "2026-08-05_1430"
    assert report_heading_time(when) == "2026-08-05 14:30 UTC"


def test_report_stamp_converts_non_utc_to_utc() -> None:
    when = datetime(2026, 8, 5, 15, 30, 0, tzinfo=ZoneInfo("Europe/London"))
    # BST = UTC+1 → 14:30 UTC
    assert report_stamp(when) == "2026-08-05_1430"
    assert report_heading_time(when) == "2026-08-05 14:30 UTC"


def test_two_lane_headline_includes_counts() -> None:
    report = FindingReport(
        confidence=59,
        summary=Summary(critical=0, high=4, medium=28, low=8),
        issues=[],
        provenance=ProvenanceBlock(fastBrainFiles=184, llmPackFiles=26, triageRouting=True),
        durationSeconds=120.0,
    )
    line = format_two_lane_headline(report)
    assert "Fast Brain: 184" in line
    assert "Slow Brain: 26" in line
    assert "4 high" in line.lower() or "High 4" in line


def test_two_lane_headline_includes_lane_seconds_when_present():
    report = FindingReport(
        confidence=70,
        summary=Summary(),
        issues=[],
        provenance=ProvenanceBlock(
            fastBrainFiles=158,
            llmPackFiles=17,
            fastBrainSeconds=2.1,
            llmSeconds=32.0,
        ),
    )
    line = format_two_lane_headline(report)
    assert "2.1s" in line or "2s" in line
    assert "32" in line


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
    assert "## Finding fields" in text
    assert "Fingerprint" in text
    assert "Occurrence" in text
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


def test_render_markdown_includes_gate_adequacy_note() -> None:
    report = FindingReport(
        confidence=75,
        summary=Summary(critical=0, high=1, medium=0, low=0),
        securityAuditConfidence=80,
    )
    md = render_markdown(
        report, mode="review", commit_go="go", push_go="no-go"
    )
    assert "[!NOTE]" in md
    assert "review-package adequacy" in md
    assert GATE_ADEQUACY_ONE_LINER.split("(")[0].strip() in md or (
        "not a" in md.lower() and "% secure" in md
    )
    assert '"% secure"' in md or "% secure" in md


def test_collapsed_duplicates_note_only_when_tools_overlap() -> None:
    plain = FindingReport(
        confidence=50,
        summary=Summary(critical=0, high=2, medium=0, low=0),
    )
    assert format_collapsed_duplicates(plain) is None

    same = FindingReport(
        confidence=50,
        summary=Summary(critical=1, high=1, medium=0, low=0),
        rawCriticalHighCount=2,
    )
    assert format_collapsed_duplicates(same) is None

    collapsed = FindingReport(
        confidence=50,
        summary=Summary(critical=0, high=2, medium=0, low=0),
        rawCriticalHighCount=4,
        rawTotalFindings=6,
    )
    assert format_collapsed_duplicates(collapsed) == (
        "4 tool rows evaluated → 2 Critical/High retained (2 not retained)"
    )


def test_render_markdown_mentions_merge_without_a_combined_severity() -> None:
    report = FindingReport(
        confidence=60,
        summary=Summary(critical=0, high=2, medium=1, low=0),
        rawCriticalHighCount=4,
        rawTotalFindings=6,
        securityAuditConfidence=70,
    )
    md = render_markdown(
        report, mode="review", commit_go="go", push_go="no-go"
    )
    assert "4 tool rows evaluated → 2 Critical/High retained (2 not retained)" in md
    assert "Unique Critical/High" not in md
    assert "High 2" in md
    assert "Medium 1" in md


def test_model_note_is_visible_and_not_counted() -> None:
    from repolens.schema import Issue

    measured = Issue(
        severity="MEDIUM",
        priority="P2",
        category="heuristic.mega_file",
        file="tests/test_deep.py",
        line=1,
        title="Mega-file",
        explanation="513 lines",
        recommendedFix="split",
        source="heuristic",
    )
    note = Issue(
        severity="HIGH",
        priority="P2",
        category="arch.readability_complexity",
        file="src/repolens/report.py",
        line=407,
        title="Function is overly complex",
        explanation="The model estimated a high score.",
        impact="harder to change",
        recommendedFix="split",
        codeExample="def smaller():\n    return 1\n",
        source="llm",
    )
    report = FindingReport(
        confidence=95,
        summary=Summary(),
        issues=[measured, note],
    )
    report.summary = report.recount_summary()
    md = render_markdown(report, mode="review", commit_go="go", push_go="go")
    assert report.summary.high == 0
    assert report.summary.medium == 1
    assert report.summary.low == 0
    assert "Function is overly complex" in md
    assert "## Model notes" in md
    assert "do not change Critical, High, Medium, or Low" in md


def test_metrics_includes_fast_brain_without_band_audits(tmp_path: Path) -> None:
    report = FindingReport(
        confidence=80,
        summary=Summary(),
        issues=[],
        provenance=ProvenanceBlock(fastBrainFiles=286, llmPackFiles=0),
    )
    text = write_markdown_report(report, tmp_path, mode="review").read_text(
        encoding="utf-8"
    )
    assert "## Metrics" in text
    assert "| Fast Brain files | 286 |" in text
    assert "| LLM pack files | 0 |" in text
    assert "### How these % are calculated" not in text


def test_metrics_and_coverage_explain_formulas(tmp_path: Path) -> None:
    report = FindingReport(
        confidence=47,
        summary=Summary(critical=0, high=1, medium=2, low=3),
        issues=[],
        durationSeconds=4337,
        securityAuditConfidence=100,
        reliabilityAuditConfidence=55,
        architectureAuditConfidence=67,
        coverage=CoverageBlock(
            covered=["sec.injection"],
            na={"sec.xss_csrf": "No web surface"},
            missed=["arch.blast_radius"],
        ),
    )
    text = write_markdown_report(report, tmp_path, mode="review").read_text(
        encoding="utf-8"
    )
    assert "How these % are calculated" in text
    assert "Why a score is low" in text
    assert "[Why](#why-a-score-is-low)" in text
    assert "[Checklist](#checklist)" in text
    assert "Reliability audit 55%" in text
    assert "Medium and Low findings do not change" in text
    assert "| Critical | 0 |" in text
    assert "| High | 1 |" in text
    assert "| Medium | 2 |" in text
    assert "| Low | 3 |" in text
    assert "| Duration | 1h 12m 17s |" in text
    assert "| Duration | 4337" not in text
    assert "### Answered" in text
    assert "Injection & unsafe code (sec.injection)" in text
    assert "### Does not apply" in text
    assert "XSS / CSRF / web surface (sec.xss_csrf)" in text
    assert "No web surface" in text
    assert "### Not answered" in text
    assert "Scoped change blast radius" in text
    assert "Re-run" in text
    assert "### N/A" not in text
    assert "### Missed" not in text


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


def test_markdown_notes_llm_bypassed_triage_over_skipped(tmp_path: Path) -> None:
    report = FindingReport(
        confidence=80,
        summary=Summary(),
        issues=[],
        llmSkipped=True,
        llmBypassed=True,
    )
    text = write_markdown_report(report, tmp_path, mode="review").read_text(
        encoding="utf-8"
    )
    assert "**LLM:** bypassed (scanners clean at triage floor)" in text
    assert "no fingerprint delta" not in text


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
    assert "coverage:sec.xss_csrf" not in text.split("## Checklist")[0]
    assert "coverage:arch.testing: missed" not in text.split("## Checklist")[0]
    # Still visible under Coverage
    assert "## Checklist" in text
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


def test_floored_pass_labels_na_as_the_models_claim() -> None:
    report = FindingReport(
        confidence=75,
        summary=Summary(),
        coverage=CoverageBlock(
            na={"sec.injection": "The repository does not contain any code."},
        ),
        durabilityGaps=["metrics.vacuous_pass_confidence_floored:p1=75"],
    )
    text = render_markdown(report, mode="review", commit_go="n/a", push_go="n/a")
    assert "### Model said these do not apply" in text
    assert "The confidence floor did not accept these lines as facts" in text
    assert "The repository does not contain any code." in text

    plain = report.model_copy(update={"durabilityGaps": []})
    plain_text = render_markdown(plain, mode="review", commit_go="n/a", push_go="n/a")
    assert "### Does not apply" in plain_text
    assert "### Model said these do not apply" not in plain_text
