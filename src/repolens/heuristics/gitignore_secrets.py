"""Detect .gitignore gaps for env/secret patterns when secret-touching scripts exist."""

from __future__ import annotations

import re
from pathlib import Path

from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

_SECRET_TRIGGERS = re.compile(
    r"(password|passwd|secret|api[_-]?key|apple[_-]?id|notarize|notarytool|\.env)",
    re.IGNORECASE,
)

_REQUIRED_GITIGNORE_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.p12",
    "credentials.json",
)


def _is_secret_touching_script(relative: str, text: str) -> bool:
    name = Path(relative).name.lower()
    if "notarize" in name or "notary" in name:
        return True
    if relative.startswith("scripts/") or "/scripts/" in relative:
        if _SECRET_TRIGGERS.search(text):
            return True
    if name.endswith((".sh", ".bash", ".zsh", ".ps1", ".env", ".env.example")):
        if _SECRET_TRIGGERS.search(text):
            return True
    return False


def _gitignore_covers(gitignore_text: str, pattern: str) -> bool:
    lines = [
        line.strip()
        for line in gitignore_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    for line in lines:
        # Exact or directory-anchored match for common secret ignores.
        if line == pattern or line.endswith("/" + pattern) or line == "/" + pattern:
            return True
        if pattern == ".env" and (
            line in {".env", ".env*", ".env.*", "*.env"} or line.startswith(".env")
        ):
            return True
        if pattern == ".env.*" and line in {".env.*", ".env*", ".env"}:
            return True
    return False


def find_gitignore_secret_gaps(root: Path, entries: list[FileEntry]) -> list[Issue]:
    secret_scripts: list[str] = []
    for entry in entries:
        if not entry.path.is_file():
            continue
        try:
            text = entry.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _is_secret_touching_script(entry.relative, text):
            secret_scripts.append(entry.relative)

    if not secret_scripts:
        return []

    gitignore_path = root / ".gitignore"
    if gitignore_path.is_file():
        try:
            gitignore_text = gitignore_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            gitignore_text = ""
    else:
        gitignore_text = ""

    missing = [
        pattern
        for pattern in _REQUIRED_GITIGNORE_PATTERNS
        if not _gitignore_covers(gitignore_text, pattern)
    ]
    # Require at least .env gap to fire (core signal from acceptance criteria).
    if ".env" not in missing and ".env.*" not in missing:
        return []

    missing_env = [p for p in missing if p.startswith(".env")]
    sample = ", ".join(secret_scripts[:3])
    return [
        Issue(
            severity=Severity.MEDIUM,
            priority="P2",
            category="heuristic.gitignore_secrets",
            file=".gitignore" if gitignore_path.is_file() else secret_scripts[0],
            line=1,
            title="Gitignore missing .env / secret patterns",
            explanation=(
                f"Secret-touching scripts exist ({sample}) but .gitignore does not "
                f"ignore {', '.join(missing_env)}. Local env files may be committed."
            ),
            recommendedFix=(
                "Add `.env`, `.env.*`, and other secret file patterns to `.gitignore`, "
                "and keep real credentials in a secret manager or keychain."
            ),
            fixTiming="before launch",
        )
    ]
