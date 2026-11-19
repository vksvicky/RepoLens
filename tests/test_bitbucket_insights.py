"""Bitbucket Code Insights JSON is a rendering of one FindingReport."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from repolens.bitbucket_insights import (
    bitbucket_insights_payload,
    write_bitbucket_insights,
)
from repolens.cli import app
from repolens.issue_ids import stable_id
from repolens.schema import FindingReport, Issue, ProvenanceBlock, Severity, Summary

runner = CliRunner()


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


def test_severity_words_stay_and_body_fields_stay_out() -> None:
    payload = bitbucket_insights_payload(_report(
        _issue(severity=Severity.CRITICAL, category="sec.secret", title="Secret", source="scanner"),
        _issue(severity=Severity.HIGH, category="sec.demo", title="High", source="scanner"),
        _issue(severity=Severity.LOW, category="quality.near_clone", title="Clone"),
    ))
    assert [row["severity"] for row in payload["annotations"]] == [
        "CRITICAL", "HIGH", "LOW",
    ]
    assert "blocker" not in {row["severity"] for row in payload["annotations"]}
    assert payload["report"]["result"] == "FAILED"
    row = payload["annotations"][0]
    assert row["annotation_type"] == "BUG"
    assert row["summary"] == "Secret"
    assert "explanation" not in row
    assert "impact" not in row
    assert "codeExample" not in row


def test_medium_only_report_passes() -> None:
    payload = bitbucket_insights_payload(_report(_issue()))
    assert payload["report"]["result"] == "PASSED"
    assert payload["report"]["report_type"] == "BUG"
    assert payload["report"]["reporter"] == "RepoLens"
    assert payload["report"]["title"] == "RepoLens"


def test_scanners_only_is_security_and_a_fast_brain_row_does_not_flip_it() -> None:
    heuristic = _issue()
    plain = bitbucket_insights_payload(_report(heuristic))
    assert plain["report"]["report_type"] == "BUG"
    scanners = _report(heuristic)
    scanners.provenance = ProvenanceBlock(expandedArgv=["repolens", "review", "--scanners-only"])
    assert bitbucket_insights_payload(scanners)["report"]["report_type"] == "SECURITY"


def test_llm_unsafe_path_and_fingerprint_follow_the_gitlab_rule() -> None:
    hidden = _issue(source="llm", title="Guess", location_verified=False)
    shown = _issue(source="llm", title="Grounded", location_verified=True)
    payload = bitbucket_insights_payload(_report(
        hidden,
        shown,
        _issue(file="../etc/passwd", title="Parent"),
        _issue(file="src\\mod.py", title="Windows"),
    ))
    summaries = [row["summary"] for row in payload["annotations"]]
    assert summaries == ["Grounded", "Windows"]
    assert payload["annotations"][1]["path"] == "src/mod.py"
    stamped = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
    stamped_payload = bitbucket_insights_payload(_report(_issue(stable=stamped)))
    assert stamped_payload["annotations"][0]["external_id"] == stamped
    generated = bitbucket_insights_payload(_report(_issue()))
    assert generated["annotations"][0]["external_id"] == stable_id(
        category="heuristic.large_function",
        file="src/process.py",
        title="Large function 'process_data': 94 lines",
    )


def test_write_is_deterministic(tmp_path: Path) -> None:
    report = _report(_issue())
    first = write_bitbucket_insights(report, tmp_path / "a.json")
    second = write_bitbucket_insights(report, tmp_path / "b.json")
    assert first.read_bytes() == second.read_bytes()


def test_export_writes_bitbucket_insights(tmp_path: Path) -> None:
    report = tmp_path / "gate_review_report_2026-11-19_1200.json"
    report.write_text(_report(_issue(title="From export")).model_dump_json(), encoding="utf-8")
    dest = tmp_path / "out" / "bitbucket-insights.json"
    result = runner.invoke(app, ["export", str(report), "--bitbucket-insights", str(dest)])
    assert result.exit_code == 0, result.output
    written = json.loads(dest.read_text(encoding="utf-8"))
    assert written["annotations"][0]["summary"] == "From export"


def test_export_missing_report_exits_2(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    dest = tmp_path / "bitbucket-insights.json"
    result = runner.invoke(
        app, ["export", str(missing), "--bitbucket-insights", str(dest)]
    )
    assert result.exit_code == 2
    assert not dest.exists()


def test_export_rejects_a_second_target(tmp_path: Path) -> None:
    report = tmp_path / "gate.json"
    report.write_text(_report(_issue()).model_dump_json(), encoding="utf-8")
    dest = tmp_path / "bitbucket-insights.json"
    result = runner.invoke(app, [
        "export", str(report),
        "--bitbucket-insights", str(dest),
        "--gitlab-codequality", str(tmp_path / "gl.json"),
    ])
    assert result.exit_code == 2
    assert not dest.exists()


def test_review_writes_insights_without_calling_the_model(tmp_path: Path, monkeypatch) -> None:
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
        "review", "--path", str(root), "--out", str(out),
        "--scanners-only", "--scanners", "off",
        "--bitbucket-insights", "--format", "json",
    ])
    assert result.exit_code == 0, result.output
    payload = json.loads((out / "bitbucket-insights.json").read_text(encoding="utf-8"))
    assert payload["report"]["report_type"] == "SECURITY"
    assert isinstance(payload["annotations"], list)
    report = json.loads(next(out.glob("gate_review_report_*.json")).read_text(encoding="utf-8"))
    assert report["scannerRuns"] == []
    assert "--bitbucket-insights" in report["provenance"]["expandedArgv"]


def test_audit_does_not_grow_the_flag() -> None:
    """Registration is the CI-stable contract. Rich may clip rendered help."""
    from typer.main import get_command

    click_app = get_command(app)

    def names(command: str) -> set[str]:
        found: set[str] = set()
        for param in click_app.commands[command].params:
            found.update(getattr(param, "opts", ()) or ())
            found.update(getattr(param, "secondary_opts", ()) or ())
        return found

    assert "--bitbucket-insights" in names("review")
    assert "--bitbucket-insights" not in names("audit")


_DOCS = Path(__file__).resolve().parents[1] / "docs" / "ci.md"


def test_bitbucket_insights_snippet_posts_report_then_annotations() -> None:
    text = _DOCS.read_text(encoding="utf-8")
    start = text.index("### Bitbucket Code Insights")
    nxt = text.find("\n#", start + 1)
    snippet = text[start:nxt if nxt >= 0 else None]
    report_url = (
        "https://api.bitbucket.org/2.0/repositories/"
        "${BITBUCKET_WORKSPACE}/${BITBUCKET_REPO_SLUG}/commit/${BITBUCKET_COMMIT}/reports/repolens"
    )
    assert report_url in snippet
    assert report_url + "/annotations" in snippet
    assert "BITBUCKET_TOKEN" in snippet
    assert "print(token" not in snippet
    assert "print(os.environ" not in snippet
    assert snippet.count("repolens review") == 1
    assert "--bitbucket-insights" in snippet
    assert "range(0, len(notes), 100)" in snippet
    assert "status=0" in snippet
    assert "|| status=$?" in snippet
    assert 'exit "$status"' in snippet
    assert snippet.index("|| status=$?") < snippet.index(
        'send(root, payload["report"], "PUT")'
    )
    assert "post_status=0" in snippet
    assert "|| post_status=$?" in snippet
    assert 'exit "$post_status"' in snippet
    assert snippet.index("|| post_status=$?") < snippet.index('exit "$status"')
