"""Large-function span heuristic (Fast Brain — line spans, not cyclomatic)."""

from __future__ import annotations

import ast

from repolens.heuristics.mega_files import is_mega_file_excluded
from repolens.heuristics.paths import is_test_source
from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

MIN_FUNCTION_LINES = 80
_PYTHON = {".py"}
_TREE_SITTER_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".cs"}


def _python_large_functions(text: str) -> list[tuple[str, int, int]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    found: list[tuple[str, int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = int(getattr(node, "end_lineno", None) or node.lineno)
        span = end - node.lineno + 1
        if span >= MIN_FUNCTION_LINES:
            found.append((node.name, node.lineno, span))
    found.sort(key=lambda item: (item[1], item[0]))
    return found


def find_large_functions(files: list[FileEntry]) -> list[Issue]:
    issues: list[Issue] = []
    for entry in files:
        if not entry.path.is_file():
            continue
        if is_test_source(entry.relative) or is_mega_file_excluded(entry.relative):
            continue
        suffix = entry.path.suffix.lower()
        if suffix in _TREE_SITTER_SUFFIXES:
            continue
        if suffix not in _PYTHON:
            continue
        try:
            text = entry.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name, line, span in _python_large_functions(text):
            issues.append(
                Issue(
                    severity=Severity.MEDIUM,
                    priority="P3",
                    category="heuristic.large_function",
                    file=entry.relative,
                    line=max(line, 1),
                    title=f"Large function {name!r}: {span} lines",
                    explanation=(
                        f"{entry.relative}:{line} function {name!r} spans {span} lines "
                        f"(threshold {MIN_FUNCTION_LINES}). Long functions are harder to "
                        "read and test; this is a span check, not cyclomatic complexity."
                    ),
                    recommendedFix=(
                        "Extract helpers, split responsibilities, or shorten the function "
                        "so each unit stays under the line-span threshold."
                    ),
                    fixTiming="if time permits",
                    source="heuristic",
                )
            )
    return issues
