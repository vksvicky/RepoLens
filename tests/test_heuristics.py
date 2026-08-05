"""Heuristic pre-pass signals (stdlib-only)."""

from __future__ import annotations

from pathlib import Path

from repolens.heuristics import HeuristicResult, run_heuristics
from repolens.inventory import FileEntry
from repolens.schema import Severity


def _entry(root: Path, relative: str, *, band: int = 3) -> FileEntry:
    path = root / relative
    return FileEntry(
        path=path,
        relative=relative,
        size=path.stat().st_size if path.is_file() else 0,
        priority_band=band,
    )


def _entries_for(root: Path, *relatives: str) -> list[FileEntry]:
    return [_entry(root, rel) for rel in relatives]


def test_mega_file_at_threshold_emits_medium_and_hot_path(tmp_path: Path) -> None:
    big = tmp_path / "LocalizedString.swift"
    big.write_text("\n".join(f"let x{i} = {i}" for i in range(500)) + "\n", encoding="utf-8")
    entries = _entries_for(tmp_path, "LocalizedString.swift")

    result = run_heuristics(tmp_path, entries, mega_file_lines=500)

    assert isinstance(result, HeuristicResult)
    mega = [
        i
        for i in result.issues
        if "mega" in i.title.lower() or "large file" in i.title.lower()
    ]
    assert mega, f"expected mega-file issue, got: {[i.title for i in result.issues]}"
    assert mega[0].severity == Severity.MEDIUM
    assert mega[0].file == "LocalizedString.swift"
    assert "LocalizedString.swift" in result.hot_paths


def test_gitignore_missing_env_when_notarize_mentions_password(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    notarize = scripts / "notarize.sh"
    notarize.write_text(
        "#!/bin/bash\n"
        'export APPLE_ID_PASSWORD="$NOTARIZE_PASSWORD"\n'
        "xcrun notarytool submit app.zip\n",
        encoding="utf-8",
    )
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.pyc\nnode_modules/\n", encoding="utf-8")
    entries = _entries_for(tmp_path, "scripts/notarize.sh", ".gitignore")

    result = run_heuristics(tmp_path, entries)

    secrets = [
        i
        for i in result.issues
        if i.severity == Severity.MEDIUM
        and (
            ".env" in i.title.lower()
            or "gitignore" in i.title.lower()
            or "secret" in i.category.lower()
        )
    ]
    assert secrets, f"expected gitignore/secrets issue, got: {[i.title for i in result.issues]}"
    assert any(".env" in (i.explanation + i.recommendedFix + i.title) for i in secrets)


def test_extract_replace_sibling_pair_emits_medium_duplication(tmp_path: Path) -> None:
    views = tmp_path / "Views"
    views.mkdir()
    (views / "ExtractToolView.swift").write_text(
        "struct ExtractToolView { func run() {} }\n",
        encoding="utf-8",
    )
    (views / "ReplaceToolView.swift").write_text(
        "struct ReplaceToolView { func run() {} }\n",
        encoding="utf-8",
    )
    entries = _entries_for(
        tmp_path,
        "Views/ExtractToolView.swift",
        "Views/ReplaceToolView.swift",
    )

    result = run_heuristics(tmp_path, entries)

    dups = [
        i
        for i in result.issues
        if i.severity == Severity.MEDIUM
        and ("duplic" in i.title.lower() or "sibling" in i.title.lower())
    ]
    assert dups, f"expected sibling duplication issue, got: {[i.title for i in result.issues]}"
    joined = " ".join(i.explanation + i.title + i.file for i in dups)
    assert "ExtractToolView" in joined
    assert "ReplaceToolView" in joined


def test_todo_fixme_density_emits_low(tmp_path: Path) -> None:
    src = tmp_path / "messy.py"
    lines = ["# TODO: fix later\n", "# FIXME: broken\n"] * 8 + ["x = 1\n"] * 4
    src.write_text("".join(lines), encoding="utf-8")
    entries = _entries_for(tmp_path, "messy.py")

    result = run_heuristics(tmp_path, entries)

    todos = [
        i
        for i in result.issues
        if i.severity == Severity.LOW and "TODO" in (i.title + i.explanation)
    ]
    assert todos, f"expected TODO/FIXME density issue, got: {[i.title for i in result.issues]}"


def test_mega_file_excludes_superpowers_paths(tmp_path: Path) -> None:
    from repolens.heuristics.mega_files import is_mega_file_excluded

    assert is_mega_file_excluded(".superpowers/sdd/big.diff")
    assert is_mega_file_excluded("docs/readme.md")


def test_sibling_pairs_skip_test_fixtures(tmp_path: Path) -> None:
    views = tmp_path / "tests" / "fixtures" / "heuristics" / "siblings" / "Views"
    views.mkdir(parents=True)
    (views / "ExtractToolView.swift").write_text("struct ExtractToolView {}\n", encoding="utf-8")
    (views / "ReplaceToolView.swift").write_text("struct ReplaceToolView {}\n", encoding="utf-8")
    rel = "tests/fixtures/heuristics/siblings/Views"
    entries = _entries_for(
        tmp_path,
        f"{rel}/ExtractToolView.swift",
        f"{rel}/ReplaceToolView.swift",
    )
    result = run_heuristics(tmp_path, entries)
    dups = [i for i in result.issues if "sibling" in i.title.lower() or "duplic" in i.title.lower()]
    assert not dups


def test_scripts_hygiene_skips_markdown_playbooks(tmp_path: Path) -> None:
    md = tmp_path / "playbooks" / "security.md"
    md.parent.mkdir(parents=True)
    md.write_text(
        "# Security\nUse a password or Apple ID for notarization examples.\n",
        encoding="utf-8",
    )
    sh = tmp_path / "scripts" / "notarize.sh"
    sh.parent.mkdir(parents=True)
    sh.write_text(
        "#!/bin/bash\nexport APPLE_ID_PASSWORD=secret\nxcrun notarytool submit x\n",
        encoding="utf-8",
    )
    entries = _entries_for(tmp_path, "playbooks/security.md", "scripts/notarize.sh")
    result = run_heuristics(tmp_path, entries)
    hygiene = [i for i in result.issues if i.category == "heuristic.scripts_hygiene"]
    assert hygiene
    assert all(i.file.endswith(".sh") for i in hygiene)
    assert not any(i.file.endswith(".md") for i in hygiene)


def test_missing_dependabot_when_package_manifest_exists(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.js").write_text("console.log(1)\n", encoding="utf-8")
    entries = _entries_for(tmp_path, "package.json", "src/index.js")

    result = run_heuristics(tmp_path, entries)

    ci = [
        i
        for i in result.issues
        if i.severity == Severity.LOW
        and (
            "dependabot" in (i.title + i.explanation).lower()
            or "codeql" in (i.title + i.explanation).lower()
        )
    ]
    assert ci, f"expected CI gap issue, got: {[i.title for i in result.issues]}"
