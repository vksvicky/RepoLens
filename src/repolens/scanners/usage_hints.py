"""Best-effort package usage hints from source text (Phase 6.9).

This is **not** reachability analysis. A hit means the package name appears in
project source (import/require/use). Absence does not prove the package is
unreachable in production.
"""

from __future__ import annotations

import re
from pathlib import Path

from repolens.schema import Issue

_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".repolens",
        "node_modules",
        "vendor",
        "dist",
        "build",
        ".venv",
        "venv",
        "__pycache__",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "reports",
    }
)
_TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".pyi",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".go",
        ".rb",
        ".php",
        ".java",
        ".kt",
        ".cs",
        ".rs",
        ".swift",
        ".scala",
        ".toml",
        ".cfg",
        ".ini",
        ".yml",
        ".yaml",
        ".json",
        ".md",
        ".txt",
        ".sh",
    }
)
_MAX_FILES = 2_000
_MAX_FILE_BYTES = 400_000


def _pkg_patterns(package_name: str) -> list[re.Pattern[str]]:
    pkg = package_name.strip()
    if not pkg:
        return []
    # Common import / require shapes; case-sensitive for most ecosystems.
    escaped = re.escape(pkg)
    # Python import path may use dots for namespace pkgs.
    dotted = re.escape(pkg.replace("-", "_"))
    return [
        re.compile(rf"\bimport\s+{dotted}\b"),
        re.compile(rf"\bfrom\s+{dotted}\b"),
        re.compile(rf"""require\(\s*['"]{escaped}['"]\s*\)"""),
        re.compile(rf"""from\s+['"]{escaped}['"]"""),
        re.compile(rf"""import\(\s*['"]{escaped}['"]\s*\)"""),
        re.compile(rf"\b{escaped}\b"),
    ]


def package_referenced_in_tree(root: Path, package_name: str) -> bool:
    """True when any scanned source file appears to reference ``package_name``."""
    patterns = _pkg_patterns(package_name)
    if not patterns:
        return False
    root_res = root.resolve()
    checked = 0
    for path in root_res.rglob("*"):
        if checked >= _MAX_FILES:
            break
        if not path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() not in _TEXT_SUFFIXES and path.name not in {
            "Dockerfile",
            "Makefile",
            "Pipfile",
        }:
            continue
        try:
            if path.stat().st_size > _MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        checked += 1
        for pat in patterns:
            if pat.search(text):
                return True
    return False


def apply_usage_hints(root: Path, issues: list[Issue]) -> list[Issue]:
    """Stamp ``usageHint`` on SCA issues that have ``packageName``."""
    cache: dict[str, bool] = {}
    out: list[Issue] = []
    for issue in issues:
        pkg = (issue.packageName or "").strip()
        if not pkg or issue.category not in {"osv", "trivy"}:
            out.append(issue)
            continue
        if pkg not in cache:
            cache[pkg] = package_referenced_in_tree(root, pkg)
        found = cache[pkg]
        hint = "referenced_in_source" if found else "no_reference_found"
        detail = (
            f"Package name {pkg!r} appears in project source "
            "(import/require/text match). This is a usage hint, not reachability."
            if found
            else (
                f"No import/require/text match for {pkg!r} in scanned source. "
                "This does not prove the package is unused or unreachable."
            )
        )
        out.append(
            issue.model_copy(update={"usageHint": hint, "usageHintDetail": detail})
        )
    return out
