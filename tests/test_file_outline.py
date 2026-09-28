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


def test_empty_and_invalid_python_yield_no_symbols(tmp_path: Path) -> None:
    src = tmp_path / "blank.py"
    assert collect_symbols(src, "") == []
    assert collect_symbols(src, "   \n") == []
    assert collect_symbols(src, "def broken(\n") == []


def test_symbols_inside_try_with_and_async_method(tmp_path: Path) -> None:
    src = tmp_path / "wrapped.py"
    text = (
        "try:\n"
        "    def from_try():\n"
        "        return 1\n"
        "except Exception:\n"
        "    def from_handler():\n"
        "        return 2\n"
        "with open('x'):\n"
        "    async def from_with():\n"
        "        return 3\n"
        "class Box:\n"
        "    async def run(self):\n"
        "        return 4\n"
        "for _ in range(1):\n"
        "    def from_loop():\n"
        "        return 5\n"
        "match kind:\n"
        "    case 'a':\n"
        "        def from_match():\n"
        "            return 6\n"
    )
    names = {symbol.name for symbol in collect_symbols(src, text)}
    assert {
        "from_try",
        "from_handler",
        "from_with",
        "Box",
        "Box.run",
        "from_loop",
        "from_match",
    } <= names


def test_module_level_conditional_still_lists_the_function(tmp_path: Path) -> None:
    src = tmp_path / "guard.py"
    text = "if __name__ == '__main__':\n    def main():\n        return 1\n"
    names = {symbol.name for symbol in collect_symbols(src, text)}
    assert "main" in names


def test_small_file_returns_empty_outline(tmp_path: Path) -> None:
    src = tmp_path / "tiny.py"
    src.write_text("def a():\n    return 1\n", encoding="utf-8")
    assert format_file_outline(src, min_lines_for_outline=80) == ""
