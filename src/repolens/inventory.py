"""File inventory with ignores, size caps, and P1-first ordering."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

IGNORE_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".repolens",
    "reports",
    ".tox",
    "coverage",
    ".idea",
    ".vscode",
    # Agent / SDD scratch — not product source (self-review noise).
    ".superpowers",
}

IGNORE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".wasm",
    ".lock",
}

P1_NAME_HINTS = (
    ".env",
    "secret",
    "password",
    "credential",
    "auth",
    "jwt",
    "oauth",
    "session",
    "security",
    "crypto",
    "tls",
    "ssl",
    "firewall",
    "permission",
    "rbac",
)


@dataclass(frozen=True)
class FileEntry:
    path: Path
    relative: str
    size: int
    priority_band: int  # 1 = P1-first


@dataclass(frozen=True)
class InventoryResult:
    """Inventory after ignores/size filter, then optional ``max_files`` truncation."""

    files: list[FileEntry]
    total_matched: int
    max_files: int
    max_bytes: int

    @property
    def truncated(self) -> bool:
        return self.total_matched > len(self.files)

    def truncation_note(self) -> str | None:
        if not self.truncated:
            return None
        cap = "uncapped" if self.max_files <= 0 else str(self.max_files)
        return (
            f"Inventory truncated: using {len(self.files)} of {self.total_matched} "
            f"matched files (max_files={cap}). "
            "Selection order: priority_band (security-name hints first), then path. "
            "Deterministic scanners still scan the full tree."
        )


def _is_under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _is_ignored(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    if any(part in IGNORE_DIR_NAMES for part in rel_parts):
        return True
    if path.suffix.lower() in IGNORE_SUFFIXES:
        return True
    name = path.name.lower()
    if name.endswith(".min.js") or name.endswith(".min.css"):
        return True
    return False


def _band_for(relative: str) -> int:
    lower = relative.lower()
    name = Path(lower).name
    if any(hint in lower or hint in name for hint in P1_NAME_HINTS):
        return 1
    if any(
        part in lower
        for part in ("controller", "service", "model", "route", "api/", "handlers")
    ):
        return 2
    return 3


def scan_inventory(
    root: Path,
    *,
    mode: str = "full",
    since: str | None = None,
    max_files: int = 200,
    max_bytes: int = 200_000,
) -> InventoryResult:
    """Walk (or diff) the tree, then keep the top ``max_files`` by priority."""
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Path is not a directory: {root}")

    if mode == "diff":
        matched = _collect_diff_entries(root, since=since, max_bytes=max_bytes)
    else:
        matched = _collect_full_entries(root, max_bytes=max_bytes)

    matched.sort(key=lambda e: (e.priority_band, e.relative))
    total = len(matched)
    if max_files <= 0:
        kept = matched
    else:
        kept = matched[:max_files]
    return InventoryResult(
        files=kept,
        total_matched=total,
        max_files=max_files,
        max_bytes=max_bytes,
    )


def list_files(
    root: Path,
    *,
    mode: str = "full",
    since: str | None = None,
    max_files: int = 200,
    max_bytes: int = 200_000,
) -> list[FileEntry]:
    return scan_inventory(
        root, mode=mode, since=since, max_files=max_files, max_bytes=max_bytes
    ).files


def _collect_full_entries(root: Path, *, max_bytes: int) -> list[FileEntry]:
    entries: list[FileEntry] = []
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        if not _is_under_root(path, root):
            continue
        if _is_ignored(path, root):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > max_bytes:
            continue
        rel = path.relative_to(root).as_posix()
        entries.append(
            FileEntry(path=path, relative=rel, size=size, priority_band=_band_for(rel))
        )
    return entries


def _collect_diff_entries(
    root: Path,
    *,
    since: str | None,
    max_bytes: int,
) -> list[FileEntry]:
    base = since or "HEAD"
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", base],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git is required for --mode diff") from exc

    if result.returncode != 0:
        # Fall back to unstaged + staged
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        names = {
            line.strip()
            for line in (result.stdout + "\n" + staged.stdout).splitlines()
            if line.strip()
        }
    else:
        names = {line.strip() for line in result.stdout.splitlines() if line.strip()}

    entries: list[FileEntry] = []
    for name in sorted(names):
        path = root / name
        if path.is_symlink() or not path.is_file() or _is_ignored(path, root):
            continue
        if not _is_under_root(path, root):
            continue
        size = path.stat().st_size
        if size > max_bytes:
            continue
        entries.append(
            FileEntry(path=path, relative=name, size=size, priority_band=_band_for(name))
        )
    return entries


def classify_fingerprint_deletions(
    root: Path, deleted_paths: list[str]
) -> tuple[list[str], list[str]]:
    """Split cache 'deleted' into removed-from-tree vs dropped-from-inventory-pack.

    Paths still present on disk were almost always truncated out of ``max_files``,
    not actually deleted.
    """
    removed: list[str] = []
    dropped: list[str] = []
    root = root.resolve()
    for rel in deleted_paths:
        path = root / rel
        try:
            if path.is_file() and not path.is_symlink():
                dropped.append(rel)
            else:
                removed.append(rel)
        except OSError:
            removed.append(rel)
    return removed, dropped


def read_excerpt(entry: FileEntry, *, max_chars: int = 12_000) -> str:
    text = entry.path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n/* … truncated by RepoLens … */\n"
