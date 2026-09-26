"""Top-level Python package discovery for grimp import graphs."""

from __future__ import annotations

import tomllib
from collections.abc import Sequence
from pathlib import Path

_ROOT_EXCLUDE_DIRS = frozenset(
    {
        "tests",
        "docs",
        ".venv",
        "venv",
        "node_modules",
        ".git",
        "build",
        "dist",
        ".tox",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
    }
)


def discover_packages(
    root: Path,
    *,
    configured: Sequence[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Return ``(package_names, durability_gaps)`` for *root*."""
    gaps: list[str] = []
    root = root.resolve()

    if configured:
        return sorted(set(configured)), gaps

    from_pyproject = _packages_from_pyproject(root, gaps)
    if from_pyproject:
        return sorted(set(from_pyproject)), gaps

    src = root / "src"
    if src.is_dir():
        names = _scan_src_layout(src)
        if names:
            return sorted(set(names)), gaps

    names = _scan_root_layout(root)
    if names:
        return sorted(set(names)), gaps

    gaps.append(f"graph.analysis_failed: no packages discovered under {root}")
    return [], gaps


def _packages_from_pyproject(root: Path, gaps: list[str]) -> list[str]:
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return []

    try:
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        gaps.append(f"graph.analysis_failed: could not parse pyproject.toml ({exc})")
        return []

    tool = data.get("tool") or {}
    names: list[str] = []

    setuptools = tool.get("setuptools") or {}
    explicit = setuptools.get("packages")
    if isinstance(explicit, list):
        names.extend(str(p) for p in explicit)

    pkg_find = setuptools.get("packages.find")
    if not isinstance(pkg_find, dict):
        packages = setuptools.get("packages")
        if isinstance(packages, dict):
            nested = packages.get("find")
            pkg_find = nested if isinstance(nested, dict) else {}
        else:
            pkg_find = {}
    if pkg_find:
        names.extend(_packages_from_setuptools_find(root, pkg_find))

    hatch = tool.get("hatch") or {}
    build = hatch.get("build") or {}
    targets = build.get("targets") or {}
    wheel = targets.get("wheel") or {}
    hatch_pkgs = wheel.get("packages")
    if isinstance(hatch_pkgs, list):
        names.extend(str(p) for p in hatch_pkgs)
    elif isinstance(hatch_pkgs, dict):
        for key, value in hatch_pkgs.items():
            if isinstance(value, str):
                names.append(value)
            else:
                names.append(str(key))

    return [n for n in names if n and not n.startswith("_")]


def _packages_from_setuptools_find(root: Path, pkg_find: dict) -> list[str]:
    where = pkg_find.get("where")
    if where is None:
        where_dirs = [root]
    elif isinstance(where, str):
        where_dirs = [root / where]
    elif isinstance(where, list):
        where_dirs = [root / str(w) for w in where]
    else:
        return []

    include = pkg_find.get("include")
    if isinstance(include, list) and include:
        return [str(p).rstrip(".*") for p in include if str(p)]

    found: list[str] = []
    for base in where_dirs:
        if not base.is_dir():
            continue
        for child in base.iterdir():
            if not child.is_dir() or child.name.startswith("_"):
                continue
            if child.name in _ROOT_EXCLUDE_DIRS:
                continue
            if (child / "__init__.py").is_file() or any(child.glob("*.py")):
                found.append(child.name)
    return found


def _scan_src_layout(src: Path) -> list[str]:
    names: list[str] = []
    for child in src.iterdir():
        if not child.is_dir() or child.name.startswith("_"):
            continue
        if (child / "__init__.py").is_file() or any(child.glob("*.py")):
            names.append(child.name)
    return names


def _scan_root_layout(root: Path) -> list[str]:
    names: list[str] = []
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("_"):
            continue
        if child.name in _ROOT_EXCLUDE_DIRS:
            continue
        if (child / "__init__.py").is_file():
            names.append(child.name)
    return names
