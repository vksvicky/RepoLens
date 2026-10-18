"""Boolean flag parameters that select a second behavior (heuristic.boolean_flag)."""

from __future__ import annotations

from pathlib import Path

from repolens.heuristics.boolean_flags import find_boolean_flags
from repolens.inventory import FileEntry
from repolens.schema import Severity


def _entry(tmp_path: Path, rel: str, content: str) -> FileEntry:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return FileEntry(path=path, relative=rel, size=len(content), priority_band=2)


def test_branch_on_bool_parameter_flags(tmp_path: Path) -> None:
    code = """
def save(row, dry_run: bool = False):
    if dry_run:
        return
    write(row)

def forward(row, dry_run: bool = False):
    return write(row, dry_run)

def save_plain(row, dry_run=False):
    if not dry_run:
        write(row)
"""
    entry = _entry(tmp_path, "src/save.py", code)
    issues = find_boolean_flags([entry])
    lines = [i.line for i in issues]
    assert lines == [2, 10]
    assert issues[0].category == "heuristic.boolean_flag"
    assert issues[0].severity == Severity.LOW
    assert issues[0].priority == "P3"
    assert "dry_run" in issues[0].title


def test_call_default_bool_is_not_a_flag(tmp_path: Path) -> None:
    code = """
def option_json():
    return False

def export(as_json: bool = option_json()):
    if as_json:
        return "json"
    return "text"

def save(row, dry_run: bool = False):
    if dry_run:
        return
    write(row)
"""
    entry = _entry(tmp_path, "src/export.py", code)
    issues = find_boolean_flags([entry])
    assert [issue.line for issue in issues] == [10]
    assert "dry_run" in issues[0].title


def test_annotation_forms_receiver_and_nested_defs(tmp_path: Path) -> None:
    code = """
class Worker:
    def run(self, dry_run: bool = False):
        if dry_run:
            return

def union(flag: bool | None = None):
    if not flag:
        return

def quoted(flag: "bool" = False):
    if flag:
        return

def listed(flag: list[bool]):
    if flag:
        return

def qualified(flag: builtins.bool = False):
    if flag:
        return

def opts(row, *, dry_run: bool = False):
    def inner():
        return 1
    async def also():
        return 2
    if other:
        return
    if dry_run:
        return
"""
    entry = _entry(tmp_path, "src/forms.py", code)
    issues = find_boolean_flags([entry])
    lines = [issue.line for issue in issues]
    assert lines == [3, 7, 11, 19, 23]


def test_missing_file_and_syntax_error(tmp_path: Path) -> None:
    missing = FileEntry(
        path=tmp_path / "src" / "gone.py",
        relative="src/gone.py",
        size=0,
        priority_band=2,
    )
    broken = _entry(tmp_path, "src/broken.py", "def broken !!!")
    assert find_boolean_flags([missing, broken]) == []


def test_skips_tests_and_syntax_errors(tmp_path: Path) -> None:
    test_code = """
def test_save(dry_run: bool = False):
    if dry_run:
        return
"""
    files = [
        _entry(tmp_path, "tests/test_save.py", test_code),
        _entry(tmp_path, "src/broken.py", "def broken !!!"),
    ]
    assert find_boolean_flags(files) == []


def test_js_go_rust_boolean_flags(tmp_path: Path) -> None:
    js = """
function save(row, dryRun: boolean) {
  if (dryRun) return;
  write(row);
}
function forward(row, dryRun: boolean) {
  return write(row, dryRun);
}
"""
    go = """
func save(row string, dryRun bool) {
    if dryRun { return }
    write(row)
}
func forward(row string, dryRun bool) string {
    return write(row, dryRun)
}
"""
    rust = """
fn save(row: String, dry_run: bool) {
    if dry_run { return; }
    write(row);
}
fn forward(row: String, dry_run: bool) {
    write(row, dry_run);
}
"""
    files = [
        _entry(tmp_path, "src/save.ts", js),
        _entry(tmp_path, "src/save.go", go),
        _entry(tmp_path, "src/save.rs", rust),
    ]
    issues = find_boolean_flags(files)
    flagged = {(i.file, i.line) for i in issues}
    assert flagged == {("src/save.ts", 2), ("src/save.go", 2), ("src/save.rs", 2)}
