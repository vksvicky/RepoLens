"""AST line ranges for function-local and TYPE_CHECKING import scopes."""

from __future__ import annotations

import ast
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScopeRanges:
    function_ranges: tuple[tuple[int, int], ...]
    type_checking_ranges: tuple[tuple[int, int], ...]


_EMPTY = ScopeRanges(function_ranges=(), type_checking_ranges=())


def file_scope_ranges(path: Path) -> ScopeRanges:
    """Return inclusive line ranges for functions and TYPE_CHECKING blocks in *path*."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return _EMPTY
    return _ranges_from_tree(tree)


def line_in_ranges(line: int, ranges: Sequence[tuple[int, int]]) -> bool:
    return any(start <= line <= end for start, end in ranges)


def _span(node: ast.AST) -> tuple[int, int]:
    start = node.lineno
    end = node.end_lineno if node.end_lineno is not None else node.lineno
    return start, end


def _is_type_checking_test(node: ast.expr) -> bool:
    if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING":
        return True
    if isinstance(node, ast.Attribute) and node.attr == "TYPE_CHECKING":
        return True
    return False


def _ranges_from_tree(tree: ast.AST) -> ScopeRanges:
    function_ranges: list[tuple[int, int]] = []
    type_checking_ranges: list[tuple[int, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_ranges.append(_span(node))
        elif isinstance(node, ast.If) and _is_type_checking_test(node.test):
            type_checking_ranges.append(_span(node))

    return ScopeRanges(
        function_ranges=tuple(function_ranges),
        type_checking_ranges=tuple(type_checking_ranges),
    )
