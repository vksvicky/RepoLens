"""Mega-file heuristic should skip docs / Xcode noise by default."""

from __future__ import annotations

from pathlib import Path

from repolens.config import DeepConfig
from repolens.heuristics.mega_files import find_mega_files
from repolens.inventory import FileEntry
from repolens.path_globs import DEFAULT_REVIEW_SKIP_GLOBS


def _entry(root: Path, relative: str) -> FileEntry:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    return FileEntry(
        path=path,
        relative=relative,
        size=path.stat().st_size if path.is_file() else 0,
        priority_band=3,
    )


def _write_mega(path: Path, lines: int = 600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"line{i}" for i in range(lines)) + "\n", encoding="utf-8")


def test_pbxproj_mega_file_excluded(tmp_path: Path) -> None:
    rel = "App.xcodeproj/project.pbxproj"
    _write_mega(tmp_path / rel)
    entries = [_entry(tmp_path, rel)]
    issues, hot = find_mega_files(entries, mega_file_lines=500)
    assert issues == []
    assert hot == []


def test_docs_markdown_mega_file_excluded(tmp_path: Path) -> None:
    rel = "docs/FOO.md"
    _write_mega(tmp_path / rel)
    entries = [_entry(tmp_path, rel)]
    issues, hot = find_mega_files(entries, mega_file_lines=500)
    assert issues == []
    assert hot == []


def test_xcuserdata_mega_file_excluded(tmp_path: Path) -> None:
    rel = "App.xcodeproj/xcuserdata/user.xcuserdatad/xcschemes/xcschememanagement.plist"
    _write_mega(tmp_path / rel)
    entries = [_entry(tmp_path, rel)]
    issues, _ = find_mega_files(entries, mega_file_lines=500)
    assert issues == []


def test_generated_trees_are_not_mega_files(tmp_path: Path) -> None:
    """bin/, gen/, and test_output/ are build output, not source to split."""
    for rel in (
        "bin/device-settings.json",
        "gen/006/Rez.mcgen",
        "test_output/visual_report.html",
    ):
        _write_mega(tmp_path / rel, lines=746)
    entries = [_entry(tmp_path, rel) for rel in (
        "bin/device-settings.json",
        "gen/006/Rez.mcgen",
        "test_output/visual_report.html",
    )]
    issues, hot = find_mega_files(entries, mega_file_lines=500)
    assert issues == []
    assert hot == []


def test_extra_skip_globs_join_mega_and_project_paths() -> None:
    cfg = DeepConfig(
        mega_file_exclude_globs=["**/*.md"],
        skip_paths=["**/fixtures/**"],
    )
    assert cfg.extra_skip_globs() == ["**/*.md", "**/fixtures/**"]
    assert DeepConfig().extra_skip_globs() == []


def test_project_skip_path_is_added_to_the_defaults(tmp_path: Path) -> None:
    rel = "vendor/big_generated.json"
    _write_mega(tmp_path / rel, lines=600)
    source = "src/app.py"
    _write_mega(tmp_path / source, lines=600)
    entries = [_entry(tmp_path, rel), _entry(tmp_path, source)]
    issues, _hot = find_mega_files(
        entries,
        mega_file_lines=500,
        exclude_globs=(*DEFAULT_REVIEW_SKIP_GLOBS, "**/vendor/**"),
    )
    assert [issue.file for issue in issues] == [source]


def test_localized_string_swift_still_fires(tmp_path: Path) -> None:
    rel = "LocalizedString.swift"
    _write_mega(tmp_path / rel, lines=600)
    entries = [_entry(tmp_path, rel)]
    issues, hot = find_mega_files(entries, mega_file_lines=500)
    assert len(issues) == 1
    assert issues[0].file == rel
    assert rel in hot
