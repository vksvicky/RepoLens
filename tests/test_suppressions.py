"""Phase 6.7: .repolens-ignore + inline disable comments."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from repolens.schema import Issue, Severity
from repolens.suppressions import (
    IGNORE_FILENAME,
    apply_suppressions,
    append_ignore_entry,
    load_ignore_file,
    parse_disable_lines,
)


def _issue(
    *,
    file: str = "src/a.py",
    line: int = 10,
    category: str = "sec.injection",
    title: str = "demo",
    source: str = "llm",
    severity: Severity = Severity.MEDIUM,
    stable_id: str | None = "11111111-1111-4111-8111-111111111111",
) -> Issue:
    kwargs: dict = dict(
        severity=severity,
        priority="P2",
        category=category,
        file=file,
        line=line,
        title=title,
        explanation="x",
        recommendedFix="fix",
        codeExample="ok" if severity in {Severity.CRITICAL, Severity.HIGH} else "",
        source=source,  # type: ignore[arg-type]
        stableId=stable_id,
    )
    if severity in {Severity.CRITICAL, Severity.HIGH}:
        kwargs["impact"] = "Attacker may exploit this."
        kwargs["priority"] = "P1"
        kwargs["codeExample"] = "return safe()"
    return Issue(**kwargs)


def test_load_ignore_matches_stable_id(tmp_path: Path) -> None:
    ignore = tmp_path / IGNORE_FILENAME
    ignore.write_text(
        """
[[ignore]]
stableId = "11111111-1111-4111-8111-111111111111"
reason = "false_positive"
note = "test fixture"
""",
        encoding="utf-8",
    )
    entries = load_ignore_file(tmp_path)
    assert len(entries) == 1
    active, suppressed = apply_suppressions(tmp_path, [_issue()])
    assert active == []
    assert len(suppressed) == 1
    assert suppressed[0].reason == "false_positive"
    assert suppressed[0].mechanism == "ignore_file"


def test_expired_ignore_inactive(tmp_path: Path) -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    (tmp_path / IGNORE_FILENAME).write_text(
        f"""
[[ignore]]
stableId = "11111111-1111-4111-8111-111111111111"
reason = "wont_fix"
expires = "{yesterday}"
""",
        encoding="utf-8",
    )
    active, suppressed = apply_suppressions(tmp_path, [_issue()])
    assert len(active) == 1
    assert suppressed == []


def test_file_category_fingerprint(tmp_path: Path) -> None:
    (tmp_path / IGNORE_FILENAME).write_text(
        """
[[ignore]]
file = "src/a.py"
category = "sec.injection"
reason = "accepted_risk"
""",
        encoding="utf-8",
    )
    active, suppressed = apply_suppressions(
        tmp_path, [_issue(stable_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")]
    )
    assert active == []
    assert suppressed[0].mechanism == "ignore_file"


def test_disable_next_line_suppresses_llm_not_scanner(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text(
        "# repolens:disable-next-line\n"
        "eval(user_input)\n",
        encoding="utf-8",
    )
    llm = _issue(line=2, source="llm")
    scan = _issue(
        line=2,
        source="scanner",
        stable_id="22222222-2222-4222-8222-222222222222",
        title="scanner hit",
    )
    active, suppressed = apply_suppressions(tmp_path, [llm, scan])
    assert len(active) == 1
    assert active[0].source == "scanner"
    assert len(suppressed) == 1
    assert suppressed[0].mechanism == "disable_comment"


def test_disable_block_range(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text(
        "# repolens:disable\n"
        "x = 1\n"
        "y = 2\n"
        "# repolens:enable\n"
        "z = 3\n",
        encoding="utf-8",
    )
    in_block = _issue(line=2, source="heuristic")
    after = _issue(
        line=5,
        source="heuristic",
        stable_id="33333333-3333-4333-8333-333333333333",
        title="after",
    )
    active, suppressed = apply_suppressions(tmp_path, [in_block, after])
    assert [i.line for i in active] == [5]
    assert [s.issue.line for s in suppressed] == [2]


def test_parse_disable_lines_slash_comments() -> None:
    text = "// repolens:disable-next-line\nfoo();\n"
    lines = parse_disable_lines(text)
    assert 2 in lines


def test_append_ignore_entry_roundtrip(tmp_path: Path) -> None:
    path = append_ignore_entry(
        tmp_path,
        stable_id="11111111-1111-4111-8111-111111111111",
        reason="false_positive",
        note="from feedback",
    )
    assert path.name == IGNORE_FILENAME
    entries = load_ignore_file(tmp_path)
    assert entries[0].stable_id == "11111111-1111-4111-8111-111111111111"
    assert entries[0].reason == "false_positive"


def test_ignore_requires_reason(tmp_path: Path) -> None:
    (tmp_path / IGNORE_FILENAME).write_text(
        """
[[ignore]]
stableId = "11111111-1111-4111-8111-111111111111"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="reason"):
        load_ignore_file(tmp_path)


def test_disable_rejects_path_escape(tmp_path: Path) -> None:
    """Issue file paths must stay under the project root."""
    outside = tmp_path.parent / f"repolens-outside-{tmp_path.name}.txt"
    outside.write_text("# repolens:disable-next-line\nsecret\n", encoding="utf-8")
    try:
        # Point at a path that would escape if joined naively
        rel = f"../{outside.name}"
        issue = _issue(file=rel, line=2, source="llm")
        active, suppressed = apply_suppressions(tmp_path, [issue])
        assert suppressed == []
        assert len(active) == 1
    finally:
        outside.unlink(missing_ok=True)
