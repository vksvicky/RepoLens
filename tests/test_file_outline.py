"""File structure outlines for explain context."""

from __future__ import annotations

from pathlib import Path

from repolens.file_outline import collect_symbols, format_file_outline


def test_python_outline_lists_large_functions(tmp_path: Path) -> None:
    src = tmp_path / "big.py"
    # Build a multi-function file with realistic sizes
    parts = [
        "def tiny():\n    return 1\n",
        "def medium():\n" + ("    x = 1\n" * 40),
        "def large():\n" + ("    y = 2\n" * 120),
    ]
    src.write_text("\n".join(parts), encoding="utf-8")
    outline = format_file_outline(src, min_lines_for_outline=10)
    assert "large" in outline
    assert "medium" in outline
    assert "function" in outline
    assert "lines" in outline


def test_python_outline_includes_class_methods(tmp_path: Path) -> None:
    src = tmp_path / "mod.py"
    body = "    def method(self):\n" + ("        pass\n" * 30)
    src.write_text(f"class Foo:\n{body}\n", encoding="utf-8")
    syms = collect_symbols(src, src.read_text(encoding="utf-8"))
    names = {s.name for s in syms}
    assert "Foo" in names
    assert "Foo.method" in names


def test_small_file_returns_empty_outline(tmp_path: Path) -> None:
    src = tmp_path / "tiny.py"
    src.write_text("def a():\n    return 1\n", encoding="utf-8")
    assert format_file_outline(src, min_lines_for_outline=80) == ""
