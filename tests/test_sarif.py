"""Phase 6.4: anchor resolve + anchored SARIF export."""

from __future__ import annotations

import json
from pathlib import Path

from repolens.anchor import resolve_anchor
from repolens.sarif import build_sarif_log, write_sarif_report
from repolens.schema import FindingReport, Issue, Severity, Summary


def _issue(
    *,
    file: str,
    line: int,
    title: str = "demo finding",
    source: str | None = "llm",
    anchor_quote: str | None = None,
    category: str = "sec.demo",
) -> Issue:
    kwargs: dict = dict(
        severity=Severity.HIGH,
        priority="P1",
        category=category,
        file=file,
        line=line,
        title=title,
        explanation="x",
        impact="Attacker may exploit this in production.",
        recommendedFix="Fix it",
        codeExample="# fix",
        source=source,
    )
    if anchor_quote is not None:
        kwargs["anchorQuote"] = anchor_quote
    return Issue(**kwargs)


def test_resolve_anchor_finds_exact_quote(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    path.write_text("a = 1\nsecret = 'x'\nb = 2\n", encoding="utf-8")
    loc = resolve_anchor(tmp_path, "app.py", "secret = 'x'")
    assert loc is not None
    assert loc.start_line == 2
    assert loc.end_line == 2
    assert loc.start_column >= 1


def test_resolve_anchor_wrong_quote_returns_none(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("a = 1\n", encoding="utf-8")
    assert resolve_anchor(tmp_path, "app.py", "not in file") is None


def test_resolve_anchor_missing_file_returns_none(tmp_path: Path) -> None:
    assert resolve_anchor(tmp_path, "missing.py", "x") is None


def test_sarif_includes_scanner_without_quote(tmp_path: Path) -> None:
    (tmp_path / "wf.yml").write_text("permissions: write-all\n", encoding="utf-8")
    report = FindingReport(
        confidence=80,
        summary=Summary(medium=1),
        issues=[
            _issue(
                file="wf.yml",
                line=1,
                source="scanner",
                category="checkov",
                title="CKV: write-all",
            )
        ],
    )
    log = build_sarif_log(report, tmp_path)
    results = log["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["locations"][0]["physicalLocation"]["region"]["startLine"] == 1


def test_sarif_omits_unverified_llm_without_resolvable_anchor(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print(1)\n", encoding="utf-8")
    report = FindingReport(
        confidence=50,
        summary=Summary(high=1),
        issues=[
            _issue(
                file="app.py",
                line=99,  # hallucinated
                source="llm",
                anchor_quote="definitely not here",
            )
        ],
    )
    log = build_sarif_log(report, tmp_path)
    assert log["runs"][0]["results"] == []
    assert report.issues[0].locationVerified is False


def test_sarif_includes_llm_when_anchor_resolves(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("safe = 1\neval(user)\n", encoding="utf-8")
    report = FindingReport(
        confidence=50,
        summary=Summary(high=1),
        issues=[
            _issue(
                file="app.py",
                line=1,  # wrong hint — anchor wins
                source="llm",
                anchor_quote="eval(user)",
            )
        ],
    )
    log = build_sarif_log(report, tmp_path)
    results = log["runs"][0]["results"]
    assert len(results) == 1
    region = results[0]["locations"][0]["physicalLocation"]["region"]
    assert region["startLine"] == 2
    assert report.issues[0].locationVerified is True


def test_write_sarif_report_creates_file(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x=1\n", encoding="utf-8")
    report = FindingReport(
        confidence=70,
        summary=Summary(),
        issues=[_issue(file="a.py", line=1, source="scanner", category="semgrep")],
    )
    out = write_sarif_report(report, tmp_path, out_dir=tmp_path / "reports", mode="review")
    assert out is not None
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["version"] == "2.1.0"
    assert data["runs"][0]["results"]
