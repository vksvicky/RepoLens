"""Tests for parameter list heuristic (heuristic.long_parameter_list)."""

from __future__ import annotations

from pathlib import Path

from repolens.heuristics.parameter_lists import find_long_parameter_lists
from repolens.inventory import FileEntry
from repolens.schema import Severity


def _entry(tmp_path: Path, rel: str, content: str) -> FileEntry:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return FileEntry(path=path, relative=rel, size=len(content), priority_band=2)


def test_six_parameters_passes_seven_flags(tmp_path: Path) -> None:
    code = """
def clean_fn(a, b, c, d, e, f):
    return a + b

def long_fn(a, b, c, d, e, f, g):
    return a + b
"""
    entry = _entry(tmp_path, "src/api.py", code)
    issues = find_long_parameter_lists([entry])

    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "heuristic.long_parameter_list"
    assert issue.line == 5
    assert issue.priority == "P3"
    assert issue.severity == Severity.LOW
    assert "long_fn" in issue.title
    assert "7 or more" in issue.explanation


def test_method_drops_self_and_cls(tmp_path: Path) -> None:
    code = """
class Worker:
    def method_ok(self, a, b, c, d, e, f):
        pass

    @classmethod
    def clsmethod_ok(cls, a, b, c, d, e, f):
        pass

    def method_bad(self, a, b, c, d, e, f, g):
        pass
"""
    entry = _entry(tmp_path, "src/worker.py", code)
    issues = find_long_parameter_lists([entry])

    assert len(issues) == 1
    assert issues[0].line == 10
    assert "method_bad" in issues[0].title


def test_varargs_and_kwargs_excluded_pos_kw_only_included(tmp_path: Path) -> None:
    code = """
# 6 counted params + *args + **kwargs -> passes
def mixed_ok(a, b, c, d, e, f, *args, **kwargs):
    pass

# 7 counted params (posonly + normal + kwonly via *args) -> flags
def mixed_bad(a, /, b, c, d, *args, e, f, g, **kwargs):
    pass
"""
    entry = _entry(tmp_path, "src/mixed.py", code)
    issues = find_long_parameter_lists([entry])

    assert len(issues) == 1
    assert issues[0].line == 7
    assert "mixed_bad" in issues[0].title


def test_skips_test_files_and_handles_syntax_errors(tmp_path: Path) -> None:
    test_code = """
def test_something(a, b, c, d, e, f, g, h, i):
    pass
"""
    test_entry = _entry(tmp_path, "tests/test_foo.py", test_code)
    broken_entry = _entry(tmp_path, "src/broken.py", "def broken syntax !!!")

    issues = find_long_parameter_lists([test_entry, broken_entry])
    assert issues == []


def test_js_go_rust_parameter_lists(tmp_path: Path) -> None:
    js = """
function short(a, b, c, d, e, f) { return a; }
function long(a, b, c, d, e, f, g) { return a; }
"""
    go = """
func short(a, b, c, d, e, f int) int { return a }
func long(a, b, c, d, e, f, g int) int { return a }
"""
    rust = """
fn short(a: i32, b: i32, c: i32, d: i32, e: i32, f: i32) -> i32 { a }
fn long(a: i32, b: i32, c: i32, d: i32, e: i32, f: i32, g: i32) -> i32 { a }
"""
    files = [
        _entry(tmp_path, "src/api.js", js),
        _entry(tmp_path, "src/api.go", go),
        _entry(tmp_path, "src/api.rs", rust),
    ]
    issues = find_long_parameter_lists(files)
    flagged = {(i.file, i.line) for i in issues}
    assert flagged == {("src/api.js", 3), ("src/api.go", 3), ("src/api.rs", 3)}
    assert all("7 or more" in i.explanation for i in issues)
