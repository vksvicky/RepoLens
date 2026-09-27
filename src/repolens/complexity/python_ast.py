# src/repolens/complexity/python_ast.py
"""Python cyclomatic + cognitive complexity via stdlib ``ast`` (B2)."""

from __future__ import annotations

import ast
from typing import Iterable

from repolens.complexity.types import FunctionComplexity

# Control-flow nodes that increment McCabe (+1 each).
_CYCLO_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.Assert,
    ast.IfExp,
    ast.comprehension,
)

# Nodes that break linear flow for cognitive complexity (+1 + nesting).
# Handled explicitly in ``_cog_node`` (If / For / While / With / Try / BoolOp / IfExp).


def analyse_python_source(source: str, *, path: str) -> list[FunctionComplexity]:
    """Return complexity for every function/method in ``source``."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out: list[FunctionComplexity] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(_analyse_function(node, path=path))
    return out


def analyse_python_file(path: str, source: str | None = None) -> list[FunctionComplexity]:
    if source is None:
        from pathlib import Path

        source = Path(path).read_text(encoding="utf-8")
    return analyse_python_source(source, path=path)


def _analyse_function(
    fn: ast.FunctionDef | ast.AsyncFunctionDef, *, path: str
) -> FunctionComplexity:
    start = getattr(fn, "lineno", 1) or 1
    end = getattr(fn, "end_lineno", None) or _max_lineno(fn) or start
    return FunctionComplexity(
        name=fn.name,
        path=path,
        start_line=start,
        end_line=end,
        cyclomatic=_cyclomatic(fn),
        cognitive=_cognitive(fn),
        language="python",
    )


def _max_lineno(node: ast.AST) -> int:
    best = getattr(node, "lineno", 0) or 0
    for child in ast.iter_child_nodes(node):
        best = max(best, _max_lineno(child))
    return best


def _cyclomatic(fn: ast.AST) -> int:
    """McCabe: 1 + decision points inside the function body (not nested defs)."""
    score = 1
    for node in _iter_body(fn):
        if isinstance(node, _CYCLO_NODES):
            score += 1
        elif isinstance(node, ast.BoolOp):
            # and/or chain: n values → n-1 decisions
            score += max(0, len(node.values) - 1)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue  # nested defs counted separately via walk at module level
    return score


def _iter_body(fn: ast.AST) -> Iterable[ast.AST]:
    """Walk descendants but do not descend into nested function/class defs."""
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _cognitive(fn: ast.AST) -> int:
    """Sonar-behavioural cognitive: +1 (+ nesting) for structural breaks in flow."""
    return _cog_visit(list(getattr(fn, "body", []) or []), nesting=0)


def _cog_visit(nodes: list[ast.AST], *, nesting: int) -> int:
    total = 0
    for node in nodes:
        total += _cog_node(node, nesting=nesting)
    return total


def _cog_node(node: ast.AST, *, nesting: int) -> int:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return 0

    if isinstance(node, ast.If):
        # if / elif chain
        score = 1 + nesting
        score += _cog_visit(node.body, nesting=nesting + 1)
        current_orelse = node.orelse
        while len(current_orelse) == 1 and isinstance(current_orelse[0], ast.If):
            # elif
            elif_node = current_orelse[0]
            score += 1 + nesting
            score += _cog_visit(elif_node.body, nesting=nesting + 1)
            current_orelse = elif_node.orelse
        if current_orelse:
            # else — +1, nest body
            score += 1
            score += _cog_visit(current_orelse, nesting=nesting + 1)
        return score

    if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
        score = 1 + nesting
        score += _cog_visit(node.body, nesting=nesting + 1)
        if node.orelse:
            score += 1
            score += _cog_visit(node.orelse, nesting=nesting + 1)
        return score

    if isinstance(node, (ast.With, ast.AsyncWith)):
        score = 1 + nesting
        score += _cog_visit(node.body, nesting=nesting + 1)
        return score

    if isinstance(node, ast.Try):
        score = 0
        score += _cog_visit(node.body, nesting=nesting)
        for handler in node.handlers:
            score += 1 + nesting
            score += _cog_visit(handler.body, nesting=nesting + 1)
        if node.orelse:
            score += _cog_visit(node.orelse, nesting=nesting)
        if node.finalbody:
            score += _cog_visit(node.finalbody, nesting=nesting)
        return score

    if isinstance(node, ast.BoolOp):
        # sequence of boolean operators: +1 per additional operand beyond first
        return max(0, len(node.values) - 1)

    if isinstance(node, ast.IfExp):
        score = 1 + nesting
        score += _cog_node(node.body, nesting=nesting + 1)
        score += _cog_node(node.orelse, nesting=nesting + 1)
        return score

    # Generic: recurse into children that aren't nested defs
    score = 0
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(child, list):  # pragma: no cover
            continue
        score += _cog_node(child, nesting=nesting)
    return score
