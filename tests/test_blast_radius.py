"""Blast-radius expansion for --git-diff packs."""

from __future__ import annotations

from pathlib import Path

from repolens.blast_radius import expand_blast_radius_paths
from repolens.inventory import FileEntry


def test_expand_blast_radius_disabled_returns_base(tmp_path: Path) -> None:
    paths = expand_blast_radius_paths(
        tmp_path, ["a.py", "b.py"], [], enabled=False
    )
    assert paths == ["a.py", "b.py"]


def test_expand_blast_radius_soft_skips_without_graph(tmp_path: Path) -> None:
    # Empty tree: graph fails; base paths preserved.
    paths = expand_blast_radius_paths(
        tmp_path, ["src/repolens/cli/app.py"], [], enabled=True
    )
    assert paths == ["src/repolens/cli/app.py"]


def test_module_path_helpers_roundtrip() -> None:
    from repolens.blast_radius import _module_to_candidates, _rel_to_module

    assert _rel_to_module("src/repolens/cli/app.py") == "src.repolens.cli.app"
    assert "src/repolens/cli/app.py" in _module_to_candidates("src.repolens.cli.app")
