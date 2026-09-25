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


def _write_pyproject(tmp_path: Path, body: str) -> None:
    (tmp_path / "pyproject.toml").write_text(body, encoding="utf-8")


def test_setuptools_explicit_packages_in_pyproject(tmp_path: Path):
    _write_pyproject(
        tmp_path,
        """
[tool.setuptools]
packages = ["pkgfromtoml", "_private", ""]
""",
    )
    names, gaps = discover_packages(tmp_path)
    assert names == ["pkgfromtoml"]
    assert gaps == []


def test_setuptools_packages_find_scans_where(tmp_path: Path):
    pkg = tmp_path / "lib" / "findme"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    _write_pyproject(
        tmp_path,
        """
[tool.setuptools.packages.find]
where = ["lib"]
""",
    )
    names, gaps = discover_packages(tmp_path)
    assert names == ["findme"]
    assert gaps == []


def test_setuptools_packages_find_uses_include_list(tmp_path: Path):
    _write_pyproject(
        tmp_path,
        """
[tool.setuptools.packages.find]
include = ["pkg.*", "other"]
""",
    )
    names, gaps = discover_packages(tmp_path)
    assert names == ["other", "pkg"]
    assert gaps == []


def test_setuptools_packages_find_default_where_is_root(tmp_path: Path):
    pkg = tmp_path / "rootpkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("x = 1\n")
    _write_pyproject(
        tmp_path,
        """
[tool.setuptools.packages.find]
""",
    )
    names, _ = discover_packages(tmp_path)
    assert "rootpkg" in names


def test_hatch_wheel_packages_list(tmp_path: Path):
    _write_pyproject(
        tmp_path,
        """
[tool.hatch.build.targets.wheel]
packages = ["hatchlisted"]
""",
    )
    names, gaps = discover_packages(tmp_path)
    assert names == ["hatchlisted"]
    assert gaps == []


def test_hatch_wheel_packages_dict(tmp_path: Path):
    _write_pyproject(
        tmp_path,
        """
[tool.hatch.build.targets.wheel]
packages = { "src/hatchpkg" = "hatchpkg", "other" = 1 }
""",
    )
    names, gaps = discover_packages(tmp_path)
    assert sorted(names) == ["hatchpkg", "other"]
    assert gaps == []


def test_malformed_pyproject_falls_back_to_src_layout(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_bytes(b"[[[not valid toml\n")
    pkg = tmp_path / "src" / "fallbackpkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    names, gaps = discover_packages(tmp_path)
    assert names == ["fallbackpkg"]
    assert any("could not parse pyproject.toml" in g for g in gaps)


def test_malformed_pyproject_falls_back_to_flat_layout(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_bytes(b"bad = \n")
    pkg = tmp_path / "flatfallback"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    names, gaps = discover_packages(tmp_path)
    assert names == ["flatfallback"]
    assert any("could not parse pyproject.toml" in g for g in gaps)
