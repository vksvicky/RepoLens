"""Resolve JS/TS (and relative Go) import specifiers to repo-relative paths."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from posixpath import normpath

_JS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mts", ".cts", ".mjs", ".cjs")
_INDEX_FILES = tuple(f"index{s}" for s in _JS_SUFFIXES)


def _is_relative(specifier: str) -> bool:
    return specifier.startswith("./") or specifier.startswith("../")


def _under_root(root: Path, relative: str) -> bool:
    try:
        (root / relative).resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _first_existing(root: Path, relative: str) -> str | None:
    rel = relative.replace("\\", "/").lstrip("/")
    if not rel or not _under_root(root, rel):
        return None
    path = root / rel
    if path.is_file():
        return rel
    if path.suffix:
        return None
    for suffix in _JS_SUFFIXES:
        candidate = rel + suffix
        if (root / candidate).is_file() and _under_root(root, candidate):
            return candidate
    if path.is_dir():
        for name in _INDEX_FILES:
            candidate = f"{rel}/{name}"
            if (root / candidate).is_file() and _under_root(root, candidate):
                return candidate
    return None


def canonicalize_import(importer: str, specifier: str, *, root: Path) -> str:
    """Map a specifier onto a repo-relative path when it is relative."""
    spec = specifier.strip().strip("'\"")
    if not spec or spec.startswith("file:"):
        return spec
    if not _is_relative(spec):
        return spec.replace("\\", "/")
    importer_posix = importer.replace("\\", "/")
    base = PurePosixPath(importer_posix).parent
    joined = normpath((base / spec).as_posix())
    if joined.startswith("../") or joined == "..":
        return spec.replace("\\", "/")
    existing = _first_existing(root, joined)
    if existing:
        return existing
    if joined.startswith("./"):
        joined = joined[2:]
    return joined.lstrip("/")
