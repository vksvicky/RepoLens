"""Script/docs credential hygiene and TODO/FIXME density signals."""

from __future__ import annotations

import re

from repolens.heuristics.paths import is_test_fixture
from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

_PASSWORD_HINT = re.compile(
    r"(password|passwd|apple[_ -]?id|notarize|notarytool|APP_PASSWORD|NOTARIZE)",
    re.IGNORECASE,
)
_KEYCHAIN_HINT = re.compile(
    r"(keychain|security find-generic-password|op read|secret.?manager|1password|vault)",
    re.IGNORECASE,
)
_TODO_HINT = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
_COMMENTED_CODE = re.compile(
    r"^\s*(#|//)\s*(def |class |function |const |let |var |import |return |if |for )",
    re.MULTILINE,
)

# Executable / shell scripts only — pedagogical markdown discussing passwords is out of scope.
_SCRIPT_SUFFIXES = {
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
}


def find_script_credential_hygiene(entries: list[FileEntry]) -> list[Issue]:
    issues: list[Issue] = []
    for entry in entries:
        path = entry.path
        if not path.is_file():
            continue
        if is_test_fixture(entry.relative):
            continue
        suffix = path.suffix.lower()
        name = path.name.lower()
        if suffix not in _SCRIPT_SUFFIXES and "notarize" not in name:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not _PASSWORD_HINT.search(text):
            continue
        if _KEYCHAIN_HINT.search(text):
            continue
        severity = (
            Severity.MEDIUM
            if "notarize" in name or "password" in text.lower()
            else Severity.LOW
        )
        issues.append(
            Issue(
                severity=severity,
                priority="P2" if severity == Severity.MEDIUM else "P3",
                category="heuristic.scripts_hygiene",
                file=entry.relative,
                line=1,
                title="Credential process hygiene: password/Apple ID without keychain guidance",
                explanation=(
                    f"{entry.relative} references passwords, Apple ID, or notarization "
                    "but does not mention keychain or a secret manager."
                ),
                recommendedFix=(
                    "Load credentials from macOS keychain, 1Password CLI, or another "
                    "secret manager; document the retrieval steps next to the script."
                ),
                fixTiming="before launch" if severity == Severity.MEDIUM else "if time permits",
            )
        )
    return issues


def find_todo_density(entries: list[FileEntry], *, min_markers: int = 8) -> list[Issue]:
    issues: list[Issue] = []
    for entry in entries:
        if not entry.path.is_file():
            continue
        try:
            text = entry.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        todo_hits = len(_TODO_HINT.findall(text))
        commented = len(_COMMENTED_CODE.findall(text))
        density = todo_hits + commented
        if density < min_markers:
            continue
        issues.append(
            Issue(
                severity=Severity.LOW,
                priority="P3",
                category="heuristic.todo_density",
                file=entry.relative,
                line=1,
                title="High TODO/FIXME / commented-out code density",
                explanation=(
                    f"{entry.relative} contains {todo_hits} TODO/FIXME markers "
                    f"and {commented} commented-out code-like lines."
                ),
                recommendedFix=(
                    "Resolve, ticket, or remove stale TODOs and dead commented code "
                    "so the file reflects current intent."
                ),
                fixTiming="if time permits",
            )
        )
    return issues
