"""Repeated unnamed numeric literals (heuristic.magic_number)."""

from __future__ import annotations

from pathlib import Path

from repolens.heuristics.magic_numbers import find_magic_numbers
from repolens.inventory import FileEntry
from repolens.schema import Severity


def _entry(tmp_path: Path, rel: str, content: str) -> FileEntry:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return FileEntry(path=path, relative=rel, size=len(content), priority_band=2)


def test_repeated_literal_flags_and_small_numbers_do_not(tmp_path: Path) -> None:
    code = """
def price(amount):
    tax = amount * 0.1
    return amount + amount * 0.1

def bounds(n):
    if n == 0 or n == 1 or n == -1:
        return n

def once(n):
    return n * 0.2
"""
    entry = _entry(tmp_path, "src/price.py", code)
    issues = find_magic_numbers([entry])
    assert len(issues) == 1
    assert issues[0].category == "heuristic.magic_number"
    assert issues[0].severity == Severity.LOW
    assert issues[0].priority == "P3"
    assert issues[0].line == 3
    assert "0.1" in issues[0].title


def test_many_literals_in_one_file_are_one_finding(tmp_path: Path) -> None:
    code = """
def dial():
    red = 255
    also = 255
    blue = 128
    other = 128
    return red, also, blue, other

def rim():
    return 74 + 74
"""
    entry = _entry(tmp_path, "tools/dial.py", code)
    issues = find_magic_numbers([entry])
    assert len(issues) == 1
    assert issues[0].line == 3
    assert "255" in issues[0].explanation
    assert "128" in issues[0].explanation
    assert "74" in issues[0].explanation


def test_nested_function_literals_stay_with_that_function(tmp_path: Path) -> None:
    code = """
def outer(n):
    def inner(m):
        return m * 2 + 2
    return n + 3
"""
    entry = _entry(tmp_path, "src/nest.py", code)
    issues = find_magic_numbers([entry])
    assert len(issues) == 1
    assert issues[0].line == 4


def test_skips_tests_and_syntax_errors(tmp_path: Path) -> None:
    test_code = """
def test_price():
    assert 0.1 + 0.1 == 0.2
"""
    files = [
        _entry(tmp_path, "tests/test_price.py", test_code),
        _entry(tmp_path, "src/broken.py", "def broken !!!"),
    ]
    assert find_magic_numbers(files) == []


def test_js_go_rust_repeated_literals(tmp_path: Path) -> None:
    js = """
function price(amount) {
  const tax = amount * 0.1;
  return amount + amount * 0.1;
}
function bounds(n) {
  if (n === 0 || n === 1) return n;
}
"""
    go = """
func price(amount float64) float64 {
    tax := amount * 0.1
    return amount + amount * 0.1
}
"""
    rust = """
fn price(amount: f64) -> f64 {
    let tax = amount * 0.1;
    amount + amount * 0.1
}
"""
    files = [
        _entry(tmp_path, "src/price.js", js),
        _entry(tmp_path, "src/price.go", go),
        _entry(tmp_path, "src/price.rs", rust),
    ]
    issues = find_magic_numbers(files)
    flagged = {(i.file, i.line) for i in issues}
    assert ("src/price.js", 3) in flagged
    assert ("src/price.go", 3) in flagged
    assert ("src/price.rs", 3) in flagged
    assert all(i.line != 7 for i in issues if i.file.endswith(".js"))
