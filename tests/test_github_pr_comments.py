"""#29 GitHub PR review comments — selection, markers, idempotent update."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from repolens.github_pr_comments import (
    build_comment_body,
    finding_marker,
    post_or_update_review_comments,
    resolve_pr_number,
    select_issues_for_comments,
)
from repolens.schema import FindingReport, Issue, Severity, Summary


def _issue(
    *,
    severity: Severity = Severity.HIGH,
    file: str = "src/a.py",
    line: int = 10,
    stable_id: str = "11111111-1111-4111-8111-111111111111",
    title: str = "demo",
) -> Issue:
    return Issue(
        severity=severity,
        priority="P1",
        category="sec.injection",
        file=file,
        line=line,
        title=title,
        explanation="x",
        impact="Attacker may exploit this.",
        recommendedFix="fix it",
        codeExample="return safe()",
        stableId=stable_id,
        source="llm",
    )


def _report(issues: list[Issue]) -> FindingReport:
    return FindingReport(
        confidence=80,
        summary=Summary(critical=0, high=len(issues), medium=0, low=0),
        issues=issues,
    )


def test_select_issues_caps_at_three() -> None:
    issues = [
        _issue(stable_id=f"11111111-1111-4111-8111-11111111111{i}", title=f"t{i}")
        for i in range(5)
    ]
    # Make first critical so it ranks first
    issues[0] = _issue(
        severity=Severity.CRITICAL,
        stable_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        title="crit",
    )
    selected = select_issues_for_comments(_report(issues), max_comments=3)
    assert len(selected) == 3
    assert selected[0].severity == Severity.CRITICAL


def test_select_skips_unsafe_path_and_missing_stable_id() -> None:
    report = _report(
        [
            _issue(file="evil:path.py"),  # colon rejected by annotation sanitiser
            _issue(stable_id="", title="no id"),
            _issue(stable_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        ]
    )
    selected = select_issues_for_comments(report)
    assert len(selected) == 1
    assert selected[0].stableId == "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


def test_marker_roundtrip() -> None:
    body = build_comment_body(_issue())
    assert finding_marker("11111111-1111-4111-8111-111111111111") in body
    assert "fix it" in body


def test_resolve_pr_number_from_event(tmp_path: Path, monkeypatch) -> None:
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"pull_request": {"number": 42}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    assert resolve_pr_number() == 42
    assert resolve_pr_number(explicit=7) == 7


def test_post_or_update_creates_then_updates() -> None:
    report = _report([_issue()])
    client = MagicMock()

    # pull head
    pull_resp = MagicMock()
    pull_resp.status_code = 200
    pull_resp.raise_for_status = MagicMock()
    pull_resp.json.return_value = {"head": {"sha": "abc123"}}

    # list comments empty then with marker
    list_empty = MagicMock()
    list_empty.status_code = 200
    list_empty.raise_for_status = MagicMock()
    list_empty.json.return_value = []

    create_resp = MagicMock()
    create_resp.status_code = 201
    create_resp.raise_for_status = MagicMock()

    list_existing = MagicMock()
    list_existing.status_code = 200
    list_existing.raise_for_status = MagicMock()
    list_existing.json.return_value = [
        {
            "id": 99,
            "body": finding_marker("11111111-1111-4111-8111-111111111111") + "\nold",
        }
    ]

    patch_resp = MagicMock()
    patch_resp.status_code = 200
    patch_resp.raise_for_status = MagicMock()

    client.get.side_effect = [list_empty, pull_resp, list_existing, pull_resp]
    client.post.return_value = create_resp
    client.patch.return_value = patch_resp

    first = post_or_update_review_comments(
        report,
        owner="o",
        repo="r",
        pr_number=1,
        token="t",
        client=client,
    )
    assert first.created == 1
    assert first.updated == 0

    second = post_or_update_review_comments(
        report,
        owner="o",
        repo="r",
        pr_number=1,
        token="t",
        client=client,
    )
    assert second.created == 0
    assert second.updated == 1
    client.patch.assert_called()


def test_post_skips_when_line_not_in_diff() -> None:
    report = _report([_issue()])
    client = MagicMock()
    list_resp = MagicMock()
    list_resp.raise_for_status = MagicMock()
    list_resp.json.return_value = []
    pull_resp = MagicMock()
    pull_resp.raise_for_status = MagicMock()
    pull_resp.json.return_value = {"head": {"sha": "abc"}}
    bad = MagicMock()
    bad.status_code = 422
    bad.text = "Validation Failed"
    client.get.side_effect = [list_resp, pull_resp]
    client.post.return_value = bad
    result = post_or_update_review_comments(
        report, owner="o", repo="r", pr_number=1, token="t", client=client
    )
    assert result.created == 0
    assert result.skipped == 1
    assert result.errors
