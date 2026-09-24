from pathlib import Path

from repolens.graph.discover import discover_packages

FIXTURES = Path(__file__).parent / "fixtures" / "graph_discover"


def test_src_layout_discovers_package(tmp_path: Path):
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("x = 1\n")
    names, gaps = discover_packages(tmp_path)
    assert names == ["mypkg"]
    assert gaps == []


def test_flat_layout(tmp_path: Path):
    pkg = tmp_path / "flatpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    names, _ = discover_packages(tmp_path)
    assert "flatpkg" in names


def test_config_override(tmp_path: Path):
    names, _ = discover_packages(tmp_path, configured=["custom"])
    assert names == ["custom"]


def test_none_found_gap(tmp_path: Path):
    names, gaps = discover_packages(tmp_path)
    assert names == []
    assert any("no packages discovered" in g for g in gaps)
