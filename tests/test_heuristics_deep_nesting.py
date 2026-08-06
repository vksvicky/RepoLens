"""Fast Brain indent-depth nesting heuristic (line/indent only — no AST)."""

from __future__ import annotations

from pathlib import Path

from repolens.heuristics import run_heuristics
from repolens.heuristics.deep_nesting import find_deep_nesting
from repolens.inventory import FileEntry
from repolens.schema import Severity
from repolens.themes import theme_id_for_category


def _entry(root: Path, relative: str, *, band: int = 3) -> FileEntry:
    path = root / relative
    return FileEntry(
        path=path,
        relative=relative,
        size=path.stat().st_size if path.is_file() else 0,
        priority_band=band,
    )


def test_deep_nesting_flags_24_space_indent_fixture(tmp_path: Path) -> None:
    """20 lines at 24-space indent (≥ 6×4) should emit heuristic.deep_nesting."""
    nested = tmp_path / "nested.py"
    body = "\n".join(" " * 24 + f"x{i} = {i}" for i in range(20)) + "\n"
    nested.write_text(body, encoding="utf-8")
    entries = [_entry(tmp_path, "nested.py")]

    issues = find_deep_nesting(entries)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "heuristic.deep_nesting"
    assert issue.source == "heuristic"
    assert issue.severity == Severity.MEDIUM
    assert issue.file == "nested.py"
    assert issue.line >= 1
    assert "nest" in issue.title.lower() or "indent" in issue.title.lower()


def test_deep_nesting_below_min_lines_is_quiet(tmp_path: Path) -> None:
    nested = tmp_path / "shallow.py"
    body = "\n".join(" " * 24 + f"x{i} = {i}" for i in range(5)) + "\n"
    nested.write_text(body, encoding="utf-8")

    assert find_deep_nesting([_entry(tmp_path, "shallow.py")]) == []


def test_deep_nesting_tabs_count_as_levels(tmp_path: Path) -> None:
    nested = tmp_path / "tabs.go"
    body = "\n".join("\t" * 6 + f"x{i} := {i}" for i in range(12)) + "\n"
    nested.write_text(body, encoding="utf-8")

    issues = find_deep_nesting([_entry(tmp_path, "tabs.go")])
    assert len(issues) == 1
    assert issues[0].category == "heuristic.deep_nesting"


def test_deep_nesting_skips_non_code_suffix(tmp_path: Path) -> None:
    md = tmp_path / "notes.md"
    body = "\n".join(" " * 24 + f"line {i}" for i in range(20)) + "\n"
    md.write_text(body, encoding="utf-8")

    assert find_deep_nesting([_entry(tmp_path, "notes.md")]) == []


def test_deep_nesting_wired_into_runner_and_theme(tmp_path: Path) -> None:
    nested = tmp_path / "deep.swift"
    body = "\n".join(" " * 24 + f"let x{i} = {i}" for i in range(20)) + "\n"
    nested.write_text(body, encoding="utf-8")
    entries = [_entry(tmp_path, "deep.swift")]

    result = run_heuristics(tmp_path, entries)

    hits = [i for i in result.issues if i.category == "heuristic.deep_nesting"]
    assert hits, f"expected deep_nesting via runner, got: {[i.category for i in result.issues]}"
    assert "deep.swift" in result.hot_paths
    assert theme_id_for_category("heuristic.deep_nesting") == "arch.readability_complexity"
