"""Repeated unnamed numeric literals inside one function."""

from __future__ import annotations

import ast

from repolens.heuristics.mega_files import is_mega_file_excluded
from repolens.heuristics.paths import is_test_source
from repolens.heuristics.polyglot import OTHER_SUFFIXES, magic_hits
from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

_PYTHON = {".py"}
_IGNORED = {0, 1, -1}
_SHOWN_LITERALS = 8


def _literal_key(value: int | float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _literals(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []

    def walk(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not func:
            return
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
            and node.value not in _IGNORED
        ):
            found.append((node.lineno, _literal_key(node.value)))
        for child in ast.iter_child_nodes(node):
            walk(child)

    walk(func)
    return found


def _issue(relative: str, lineno: int, literal: str) -> Issue:
    return Issue(
        severity=Severity.LOW,
        priority="P3",
        category="heuristic.magic_number",
        file=relative,
        line=max(lineno, 1),
        title=f"Repeated literal {literal}",
        explanation=(
            f"{relative}:{lineno} uses the unnamed number {literal} more than once "
            "in the same function. 0, 1, and -1 are ignored."
        ),
        recommendedFix=f"Name {literal} once and use that name.",
        fixTiming="if time permits",
        source="heuristic",
    )


def _unique_literals(hits: list[tuple[int, str]]) -> list[str]:
    literals: list[str] = []
    for _lineno, literal in sorted(hits, key=lambda item: (item[0], item[1])):
        if literal not in literals:
            literals.append(literal)
    return literals


def _issue_for_file(relative: str, hits: list[tuple[int, str]]) -> Issue:
    ordered = sorted(hits, key=lambda item: (item[0], item[1]))
    literals = _unique_literals(ordered)
    line = ordered[0][0]
    if len(literals) == 1:
        return _issue(relative, line, literals[0])
    shown = literals[:_SHOWN_LITERALS]
    extra = len(literals) - len(shown)
    tail = f", and {extra} more" if extra else ""
    return Issue(
        severity=Severity.LOW,
        priority="P3",
        category="heuristic.magic_number",
        file=relative,
        line=max(line, 1),
        title=f"Repeated unnamed numbers ({len(literals)})",
        explanation=(
            f"{relative}:{line} repeats {len(literals)} unnamed numbers "
            f"({', '.join(shown)}{tail}). 0, 1, and -1 are ignored."
        ),
        recommendedFix=(
            "Name the repeated sizes, limits, and colours in this file. "
            "One name per number is enough."
        ),
        fixTiming="if time permits",
        source="heuristic",
    )


def _repeated_literals(source: str, suffix: str) -> list[tuple[int, str]]:
    if suffix in OTHER_SUFFIXES:
        return magic_hits(source, suffix)
    if suffix not in _PYTHON:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        counts: dict[str, list[int]] = {}
        for lineno, key in _literals(node):
            counts.setdefault(key, []).append(lineno)
        for key, places in counts.items():
            if len(places) >= 2:
                hits.append((places[0], key))
    return hits


def find_magic_numbers(files: list[FileEntry]) -> list[Issue]:
    issues: list[Issue] = []
    for entry in files:
        if not entry.path.is_file():
            continue
        if is_test_source(entry.relative) or is_mega_file_excluded(entry.relative):
            continue
        suffix = entry.path.suffix.lower()
        try:
            source = entry.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits = _repeated_literals(source, suffix)
        if hits:
            issues.append(_issue_for_file(entry.relative, hits))
    issues.sort(key=lambda item: (item.file, item.line, item.category, item.title))
    return issues
