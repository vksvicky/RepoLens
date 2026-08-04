"""Shared scanner types and binary resolution."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from repolens.schema import Issue, ScannerRun


@dataclass
class ScannerResult:
    run: ScannerRun
    issues: list[Issue] = field(default_factory=list)


def tools_cache_dir() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "repolens" / "tools"


def resolve_binary(name: str, *, candidates: tuple[str, ...] | None = None) -> Path | None:
    """Resolve a scanner binary from PATH or the RepoLens tools cache."""
    names = candidates or (name,)
    for candidate in names:
        found = shutil.which(candidate)
        if found:
            return Path(found)
    cache = tools_cache_dir() / name
    for candidate in names:
        direct = cache / candidate
        if direct.is_file() and os.access(direct, os.X_OK):
            return direct
        # nested extract layouts
        matches = list(cache.rglob(candidate))
        for match in matches:
            if match.is_file() and os.access(match, os.X_OK):
                return match
    # Semgrep may live in a cache venv
    venv_bin = tools_cache_dir() / "semgrep-venv" / "bin" / "semgrep"
    if name == "semgrep" and venv_bin.is_file() and os.access(venv_bin, os.X_OK):
        return venv_bin
    return None


MANUAL_HINTS: dict[str, str] = {
    "gitleaks": (
        "Install gitleaks: https://github.com/gitleaks/gitleaks#installing\n"
        "  brew install gitleaks\n"
        "  # or: repolens plugins install gitleaks"
    ),
    "semgrep": (
        "Install Semgrep: https://semgrep.dev/docs/getting-started/\n"
        "  pipx install semgrep\n"
        "  # or: repolens plugins install semgrep"
    ),
    "osv": (
        "Install OSV-Scanner: https://google.github.io/osv-scanner/\n"
        "  brew install osv-scanner\n"
        "  # or: repolens plugins install osv"
    ),
}
