"""Hybrid issue IDs: stableId (v5) + runId (v4)."""

from __future__ import annotations

from repolens.issue_ids import new_run_id, stable_id, stamp_issue_ids
from repolens.schema import Issue, Severity


def _issue(*, category: str = "sec.injection", file: str = "a.py", title: str = "X") -> Issue:
    return Issue(
        severity=Severity.LOW,
        priority="P3",
        category=category,
        file=file,
        line=1,
        title=title,
        explanation="e",
        recommendedFix="f",
    )


def test_stable_id_stable_for_same_identity() -> None:
    a = stable_id(category="sec.injection", file="src/foo.py", title="Command injection")
    b = stable_id(category="sec.injection", file="src/foo.py", title="Command injection")
    assert a == b
    assert len(a) == 36  # UUID string


def test_stable_id_changes_when_identity_changes() -> None:
    a = stable_id(category="sec.injection", file="src/foo.py", title="A")
    b = stable_id(category="sec.injection", file="src/foo.py", title="B")
    assert a != b


def test_stable_id_normalizes_whitespace_and_case_on_file() -> None:
    a = stable_id(category="sec.x", file="Src/Foo.py", title="Title")
    b = stable_id(category="sec.x", file="src/foo.py", title="Title")
    assert a == b


def test_new_run_id_unique() -> None:
    ids = {new_run_id() for _ in range(20)}
    assert len(ids) == 20


def test_stamp_issue_ids_sets_both_fields() -> None:
    issue = _issue()
    stamped = stamp_issue_ids([issue])
    assert stamped[0].stableId
    assert stamped[0].runId
    assert stamped[0].stableId == stable_id(
        category=issue.category, file=issue.file, title=issue.title
    )


def test_stamp_preserves_existing_stable_id_assigns_new_run_id() -> None:
    issue = _issue().model_copy(update={"stableId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"})
    stamped = stamp_issue_ids([issue])
    assert stamped[0].stableId == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert stamped[0].runId
    assert stamped[0].runId != stamped[0].stableId
