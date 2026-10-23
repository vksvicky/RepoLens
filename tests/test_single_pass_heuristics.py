"""One read per file for the per-file Fast Brain checks."""

from __future__ import annotations

import gc
import weakref
from pathlib import Path

import pytest

from repolens.heuristics.boolean_flags import find_boolean_flags
from repolens.heuristics.deep_nesting import find_deep_nesting
from repolens.heuristics.large_functions import find_large_functions
from repolens.heuristics.logging_hygiene import find_logging_hygiene
from repolens.heuristics.magic_numbers import find_magic_numbers
from repolens.heuristics.mega_files import DEFAULT_MEGA_AND_SKIP_EXCLUDES, find_mega_files
from repolens.heuristics.parameter_lists import find_long_parameter_lists
from repolens.heuristics.runner import (
    HeuristicResult,
    _evaluate_file_heuristics,
    _read_and_evaluate,
)
from repolens.heuristics.scripts_hygiene import find_script_credential_hygiene, find_todo_density
from repolens.heuristics.transport_tls import find_transport_tls
from repolens.inventory import FileEntry


def _entry(path: Path, relative: str) -> FileEntry:
    return FileEntry(path=path, relative=relative, size=path.stat().st_size, priority_band=1)


def _key(issue) -> tuple:
    return (issue.file, issue.line, issue.category, issue.title)


def test_grouped_pass_reads_a_reviewable_file_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "main.py"
    path.write_text('url = "http://example.com/a"\n', encoding="utf-8")
    entry = _entry(path, "main.py")
    calls = {"n": 0}
    real = Path.read_text

    def counting(self: Path, *args, **kwargs):
        if self == path:
            calls["n"] += 1
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting)
    _read_and_evaluate(
        [entry],
        mega_file_lines=500,
        excludes=DEFAULT_MEGA_AND_SKIP_EXCLUDES,
    )
    assert calls["n"] == 1


def test_grouped_issues_match_the_existing_finders(tmp_path: Path) -> None:
    path = tmp_path / "main.py"
    path.write_text('url = "http://example.com/a"\n', encoding="utf-8")
    entry = _entry(path, "main.py")
    text = path.read_text(encoding="utf-8")
    grouped = _evaluate_file_heuristics(
        entry,
        text,
        mega_file_lines=500,
        excludes=DEFAULT_MEGA_AND_SKIP_EXCLUDES,
    )
    direct = []
    mega, _hots = find_mega_files([entry], mega_file_lines=500)
    direct.extend(mega)
    direct.extend(find_deep_nesting([entry]))
    direct.extend(find_large_functions([entry]))
    direct.extend(find_transport_tls([entry]))
    direct.extend(find_script_credential_hygiene([entry]))
    direct.extend(find_todo_density([entry]))
    direct.extend(find_logging_hygiene([entry]))
    direct.extend(find_long_parameter_lists([entry]))
    direct.extend(find_magic_numbers([entry]))
    direct.extend(find_boolean_flags([entry]))
    assert sorted(grouped, key=_key) == sorted(direct, key=_key)


def test_excluded_path_does_not_gain_a_boolean_flag(tmp_path: Path) -> None:
    relative = "scripts/generate_learn_file_notes.py"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text(
        "def run(flag: bool):\n    if flag:\n        return 1\n" + ("x = 1\n" * 500),
        encoding="utf-8",
    )
    entry = _entry(path, relative)
    issues = _evaluate_file_heuristics(
        entry,
        path.read_text(encoding="utf-8"),
        mega_file_lines=500,
        excludes=DEFAULT_MEGA_AND_SKIP_EXCLUDES,
    )
    assert all(issue.category != "heuristic.boolean_flag" for issue in issues)
    assert all(issue.category != "heuristic.mega_file" for issue in issues)


def test_unreadable_file_is_skipped_and_the_rest_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "bad.py"
    good = tmp_path / "good.py"
    bad.write_text("x = 1\n", encoding="utf-8")
    good.write_text('url = "http://example.com/a"\n', encoding="utf-8")
    real = Path.read_text

    def flaky(self: Path, *args, **kwargs):
        if self.name == "bad.py":
            raise OSError("unreadable")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky)
    issues = _read_and_evaluate(
        [_entry(bad, "bad.py"), _entry(good, "good.py")],
        mega_file_lines=500,
        excludes=DEFAULT_MEGA_AND_SKIP_EXCLUDES,
    )
    assert any(issue.file == "good.py" for issue in issues)
    assert all(issue.file != "bad.py" for issue in issues)


def test_result_does_not_keep_the_source_body(tmp_path: Path) -> None:
    path = tmp_path / "main.py"
    path.write_text("x = 1\n", encoding="utf-8")
    entry = _entry(path, "main.py")
    class _StandIn:
        def __init__(self, body: str) -> None:
            self.body = body

    stand_in = _StandIn(path.read_text(encoding="utf-8"))
    ref = weakref.ref(stand_in)
    _evaluate_file_heuristics(
        entry,
        stand_in.body,
        mega_file_lines=500,
        excludes=DEFAULT_MEGA_AND_SKIP_EXCLUDES,
    )
    del stand_in
    gc.collect()
    assert ref() is None
    assert "source" not in HeuristicResult.__dataclass_fields__
