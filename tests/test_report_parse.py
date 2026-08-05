"""Markdown gate report → FindingReport bootstrap parser."""

from __future__ import annotations

from pathlib import Path

from repolens.report_parse import bootstrap_markdown_from_out_dir, parse_markdown_report


SAMPLE = """# Gate review report — 2026-08-05 17:31

**Gate confidence:** 28%

## Gate verdict

- **Gate confidence:** 28% (adequacy)
- **Counts:** Critical 0 · High 1 · Medium 1 · Low 0

## P1 — Security

### [HIGH] Potential Code Injection
- **Priority:** P1
- **File:** `App/Service.swift`
- **Line:** 85
- **Category:** sec.injection
- **Explanation:** User input reaches export without sanitization.
- **Impact:** Arbitrary code in generated scripts.
- **Recommended fix:** Escape inputs before export.
- **Fix timing:** immediately
- **Code example:**

```
let escaped = escape(pattern)
```

## P2 — Bugs, reliability, performance

### [MEDIUM] Mega-file: LocalizedString.swift has 637 lines
- **Priority:** P2
- **File:** `Core/LocalizedString.swift`
- **Line:** 1
- **Category:** heuristic.mega_file
- **Explanation:** File is too large.
- **Impact:** _n/a_
- **Recommended fix:** Split the file.
- **Fix timing:** before launch

## Automated scanners

_No scanners requested or configured._
"""


def test_parse_markdown_report_extracts_issues() -> None:
    report = parse_markdown_report(SAMPLE)
    assert report is not None
    assert report.llmCompleted is True
    assert report.summary.high == 1
    assert report.summary.medium == 1
    assert report.issues[0].title == "Potential Code Injection"
    assert "escape" in report.issues[0].codeExample
    assert report.issues[1].impact == ""


def test_parse_skips_empty_skip_reports() -> None:
    text = """# Gate review report
**Gate confidence:** 55%
- **Counts:** Critical 0 · High 0 · Medium 0 · Low 0
- **LLM:** skipped (no fingerprint delta under `--changed` and no prior LLM snapshot to reuse)
## Durability gaps
- [ ] LLM skipped: no prior
"""
    assert parse_markdown_report(text) is None


def test_bootstrap_picks_richest_not_newest(tmp_path: Path) -> None:
    out = tmp_path / "reports"
    out.mkdir()
    rich = out / "gate_review_report_review_2026-08-05_1731.md"
    empty = out / "gate_review_report_review_2026-08-05_1949.md"
    rich.write_text(SAMPLE, encoding="utf-8")
    empty.write_text(
        "# Gate review report\n**Gate confidence:** 55%\n"
        "- **Counts:** Critical 0 · High 0 · Medium 0 · Low 0\n"
        "LLM skipped: no prior LLM snapshot\n",
        encoding="utf-8",
    )
    # Make empty newer
    empty.write_text(empty.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    bundled = bootstrap_markdown_from_out_dir(out)
    assert bundled is not None
    report, _, _, path = bundled
    assert path.name.endswith("1731.md")
    assert len(report.issues) == 2
