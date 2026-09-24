"""AST scope line ranges for import graph gating."""

from __future__ import annotations

from pathlib import Path

from repolens.graph.scope_tags import file_scope_ranges, line_in_ranges


def test_function_range_covers_body(tmp_path: Path) -> None:
    p = tmp_path / "a.py"
    p.write_text("def f():\n    from pkg import b\n    return 1\n")
    ranges = file_scope_ranges(p)
    assert ranges.function_ranges  # e.g. (1, 3) inclusive
    start, end = ranges.function_ranges[0]
    assert start <= 2 <= end  # import line is inside


def test_module_level_not_in_function_range(tmp_path: Path) -> None:
    p = tmp_path / "a.py"
    p.write_text("from pkg import b\n\ndef f():\n    pass\n")
    ranges = file_scope_ranges(p)
    assert not any(s <= 1 <= e for s, e in ranges.function_ranges)


def test_type_checking_range(tmp_path: Path) -> None:
    p = tmp_path / "a.py"
    p.write_text(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from pkg import b\n"
    )
    ranges = file_scope_ranges(p)
    assert any(s <= 3 <= e for s, e in ranges.type_checking_ranges)


def test_type_checking_attribute_form(tmp_path: Path) -> None:
    p = tmp_path / "a.py"
    p.write_text(
        "import typing\n"
        "if typing.TYPE_CHECKING:\n"
        "    from pkg import b\n"
    )
    ranges = file_scope_ranges(p)
    assert any(s <= 3 <= e for s, e in ranges.type_checking_ranges)


def test_line_in_ranges() -> None:
    assert line_in_ranges(2, ((1, 3),))
    assert not line_in_ranges(4, ((1, 3),))


def test_syntax_error_returns_empty(tmp_path: Path) -> None:
    p = tmp_path / "bad.py"
    p.write_text("def f(\n")
    ranges = file_scope_ranges(p)
    assert ranges.function_ranges == ()
    assert ranges.type_checking_ranges == ()
