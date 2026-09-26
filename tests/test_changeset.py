"""Git change-set path listing for --git-diff (#16)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from repolens.changeset import filter_entries_to_changeset, list_git_changed_paths
from repolens.git_refs import is_safe_git_ref
from repolens.inventory import FileEntry


def _entry(rel: str) -> FileEntry:
    return FileEntry(
        path=Path("/tmp") / rel,
        relative=rel,
        size=10,
        priority_band=2,
    )


def test_rejects_unsafe_git_ref() -> None:
    assert not is_safe_git_ref("-evil")
    assert not is_safe_git_ref("foo;rm")
    assert is_safe_git_ref("main")
    assert is_safe_git_ref("origin/main")


def test_list_git_changed_paths_union_and_normalise() -> None:
    def fake_run(argv, **_kwargs):
        out = MagicMock()
        out.returncode = 0
        out.stderr = ""
        if argv == ["git", "diff", "--name-only", "main...HEAD"]:
            out.stdout = "src/a.py\nsrc/b.py\n"
        elif argv == ["git", "diff", "--name-only", "--cached"]:
            out.stdout = "src/b.py\n"
        elif argv == ["git", "diff", "--name-only"]:
            out.stdout = "src/c.py\n"
        else:
            out.stdout = ""
        return out

    with patch("repolens.changeset.subprocess.run", side_effect=fake_run):
        with patch("repolens.changeset.git_available", return_value=True):
            paths = list_git_changed_paths(
                Path("/repo"), base="main", include_dirty=True
            )
    assert paths == ["src/a.py", "src/b.py", "src/c.py"]


def test_list_git_changed_paths_rejects_unsafe_base() -> None:
    with patch("repolens.changeset.git_available", return_value=True):
        assert list_git_changed_paths(Path("/repo"), base="-rf") == []


def test_list_git_changed_paths_empty_when_not_git() -> None:
    with patch("repolens.changeset.git_available", return_value=False):
        assert list_git_changed_paths(Path("/repo"), base="main") == []


def test_filter_entries_to_changeset_intersection() -> None:
    entries = [_entry("a.py"), _entry("b.py"), _entry("c.py")]
    filtered = filter_entries_to_changeset(entries, ["b.py", "missing.py"])
    assert [e.relative for e in filtered] == ["b.py"]


def test_filter_entries_preserves_order() -> None:
    entries = [_entry("z.py"), _entry("a.py"), _entry("m.py")]
    filtered = filter_entries_to_changeset(entries, ["m.py", "z.py"])
    assert [e.relative for e in filtered] == ["z.py", "m.py"]
