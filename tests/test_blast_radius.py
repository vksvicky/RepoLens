"""Blast-radius expansion for --git-diff packs."""

from __future__ import annotations

from pathlib import Path

from repolens.blast_radius import expand_blast_radius, expand_blast_radius_paths
from repolens.inventory import FileEntry


def test_expand_blast_radius_disabled_returns_base(tmp_path: Path) -> None:
    paths = expand_blast_radius_paths(
        tmp_path, ["a.py", "b.py"], [], enabled=False
    )
    assert paths == ["a.py", "b.py"]


def test_expand_blast_radius_soft_skips_without_graph(tmp_path: Path) -> None:
    # Empty tree: graph fails; base paths preserved with an honest note.
    result = expand_blast_radius(
        tmp_path, ["src/repolens/cli/app.py"], [], enabled=True
    )
    assert result.paths == ["src/repolens/cli/app.py"]
    assert result.note
    assert "blast-radius skipped" in result.note


def test_filter_entries_blast_radius() -> None:
    from repolens.blast_radius import filter_entries_blast_radius

    a = FileEntry(path=Path("a.py"), relative="a.py", size=1, priority_band=1)
    b = FileEntry(path=Path("b.py"), relative="b.py", size=1, priority_band=1)
    assert [e.relative for e in filter_entries_blast_radius([a, b], ["b.py"])] == ["b.py"]


def test_expand_blast_radius_adds_neighbours(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    from repolens.blast_radius import expand_blast_radius
    from repolens.graph.types import EdgeKind, GraphStatus, ImportEdge, ImportScope

    src = tmp_path / "pkg"
    src.mkdir()
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "a.py").write_text("from pkg import b\n", encoding="utf-8")
    (src / "b.py").write_text("x = 1\n", encoding="utf-8")
    entries = [
        FileEntry(path=src / "a.py", relative="pkg/a.py", size=1, priority_band=1),
        FileEntry(path=src / "b.py", relative="pkg/b.py", size=1, priority_band=1),
    ]

    class FakeResult:
        status = GraphStatus.OK
        durability_gaps: list[str] = []
        gated_edges = [
            ImportEdge(
                importer="pkg.a",
                imported="pkg.b",
                kind=EdgeKind.RUNTIME,
                scope=ImportScope.MODULE,
            )
        ]

    monkeypatch.setattr(
        "repolens.graph.build.analyse_python_graph",
        lambda root, config=None: FakeResult(),
    )
    monkeypatch.setattr(
        "repolens.config.load_config",
        lambda root: SimpleNamespace(graph=None),
    )
    result = expand_blast_radius(tmp_path, ["pkg/a.py"], entries, enabled=True)
    assert "pkg/a.py" in result.paths
    assert "pkg/b.py" in result.paths
    assert result.note and "added" in result.note


def test_module_path_helpers_roundtrip() -> None:
    from repolens.blast_radius import _module_to_candidates, _rel_to_module

    assert _rel_to_module("src/repolens/cli/app.py") == "src.repolens.cli.app"
    assert "src/repolens/cli/app.py" in _module_to_candidates("src.repolens.cli.app")
