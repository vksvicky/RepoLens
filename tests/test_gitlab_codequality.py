"""GitLab code-quality JSON is a rendering of one FindingReport."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from repolens.cli import app
from repolens.gitlab_codequality import gitlab_codequality_payload, write_gitlab_codequality
from repolens.issue_ids import stable_id
from repolens.schema import FindingReport, Issue, Severity, Summary

runner = CliRunner()
_DOCS = Path(__file__).resolve().parents[1] / "docs" / "ci.md"


def _issue(
    *,
    severity: Severity = Severity.MEDIUM,
    category: str = "heuristic.large_function",
    file: str = "src/process.py",
    line: int = 45,
    title: str = "Large function 'process_data': 94 lines",
    source: str | None = "heuristic",
    stable: str | None = None,
    location_verified: bool | None = None,
) -> Issue:
    kwargs: dict = {
        "severity": severity,
        "priority": "P1" if severity in {Severity.CRITICAL, Severity.HIGH} else "P3",
        "category": category,
        "file": file,
        "line": line,
        "title": title,
        "explanation": "Long functions are harder to review.",
        "recommendedFix": "Extract a helper.",
        "source": source,
        "stableId": stable,
        "locationVerified": location_verified,
    }
    if severity in {Severity.CRITICAL, Severity.HIGH}:
        kwargs["impact"] = "A reviewer can miss the failure."
        kwargs["codeExample"] = "def small():\n    return 1\n"
    return Issue(**kwargs)


def _report(*issues: Issue) -> FindingReport:
    return FindingReport(confidence=80, summary=Summary(), issues=list(issues))


def test_large_function_is_included_without_an_anchor() -> None:
    rows = gitlab_codequality_payload(_report(_issue()))
    assert rows == [
        {
            "description": "Large function 'process_data': 94 lines",
            "check_name": "heuristic.large_function",
            "fingerprint": stable_id(
                category="heuristic.large_function",
                file="src/process.py",
                title="Large function 'process_data': 94 lines",
            ),
            "severity": "minor",
            "location": {"path": "src/process.py", "lines": {"begin": 45}},
        }
    ]
    assert "explanation" not in rows[0]
    assert "content" not in rows[0]


def test_severity_map_uses_gitlab_names() -> None:
    rows = gitlab_codequality_payload(_report(
        _issue(severity=Severity.CRITICAL, category="sec.secret", title="Secret", source="scanner"),
        _issue(severity=Severity.HIGH, category="sec.demo", title="High", source="scanner"),
        _issue(
            severity=Severity.LOW,
            category="quality.near_clone",
            title="Clone",
            source="heuristic",
        ),
    ))
    assert [row["severity"] for row in rows] == ["critical", "major", "info"]
    assert "blocker" not in {row["severity"] for row in rows}


def test_llm_row_needs_a_verified_location() -> None:
    hidden = _issue(source="llm", title="Guess", location_verified=False)
    shown = _issue(source="llm", title="Grounded", location_verified=True)
    rows = gitlab_codequality_payload(_report(hidden, shown))
    assert [row["description"] for row in rows] == ["Grounded"]


def test_unsafe_paths_are_omitted_and_windows_slashes_are_normalized() -> None:
    rows = gitlab_codequality_payload(_report(
        _issue(file="../etc/passwd", title="Parent"),
        _issue(file="/etc/passwd", title="Absolute"),
        _issue(file="src\\mod.py", title="Windows"),
    ))
    assert [row["location"]["path"] for row in rows] == ["src/mod.py"]


def test_missing_source_on_a_heuristic_category_is_included() -> None:
    rows = gitlab_codequality_payload(_report(_issue(source=None, title="Untyped")))
    assert rows[0]["description"] == "Untyped"


def test_fingerprint_uses_the_stamped_id() -> None:
    stamped = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
    rows = gitlab_codequality_payload(_report(_issue(stable=stamped)))
    assert rows[0]["fingerprint"] == stamped


def test_write_is_deterministic(tmp_path: Path) -> None:
    report = _report(_issue())
    first = write_gitlab_codequality(report, tmp_path / "a.json")
    second = write_gitlab_codequality(report, tmp_path / "b.json")
    assert first.read_bytes() == second.read_bytes()


def test_export_writes_gitlab_codequality(tmp_path: Path) -> None:
    report = tmp_path / "gate_review_report_2026-10-30_1200.json"
    report.write_text(_report(_issue(title="From export")).model_dump_json(), encoding="utf-8")
    dest = tmp_path / "out" / "gl-code-quality-report.json"
    result = runner.invoke(app, ["export", str(report), "--gitlab-codequality", str(dest)])
    assert result.exit_code == 0, result.output
    written = json.loads(dest.read_text(encoding="utf-8"))
    assert written[0]["description"] == "From export"


def test_export_missing_report_exits_2(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    dest = tmp_path / "gl-code-quality-report.json"
    result = runner.invoke(app, ["export", str(missing), "--gitlab-codequality", str(dest)])
    assert result.exit_code == 2
    assert not dest.exists()


def test_review_writes_gitlab_file_without_calling_the_model(
    tmp_path: Path, monkeypatch,
) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("model called")

    monkeypatch.setattr("repolens.llm_structured.analyze_structured", boom)
    monkeypatch.setattr("repolens.pipeline.run.analyze_structured", boom, raising=False)
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text(
        "def add(left, right):\n    return left + right\n",
        encoding="utf-8",
    )
    out = tmp_path / "reports"
    result = runner.invoke(app, [
        "review",
        "--path", str(root),
        "--out", str(out),
        "--scanners-only",
        "--scanners", "off",
        "--gitlab-codequality",
        "--format", "json",
    ])
    assert result.exit_code == 0, result.output
    payload = json.loads((out / "gl-code-quality-report.json").read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    report = json.loads(next(out.glob("gate_review_report_*.json")).read_text(encoding="utf-8"))
    assert report["scannerRuns"] == []


def test_gitlab_ci_doc_publishes_the_codequality_report() -> None:
    text = _DOCS.read_text(encoding="utf-8")
    assert "--gitlab-codequality" in text
    assert "codequality: reports/gl-code-quality-report.json" in text


def test_github_sarif_upload_uses_the_action_report() -> None:
    text = _DOCS.read_text(encoding="utf-8")
    assert "security-events: write" in text
    assert "uses: github/codeql-action/upload-sarif@v3" in text
    assert "sarif_file: reports/" in text
    assert "repolens review --path . --ci --scanners-only --sarif" not in text
