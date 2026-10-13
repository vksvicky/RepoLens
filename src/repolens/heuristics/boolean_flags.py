"""Boolean parameters that choose a second behavior inside the same function."""

from __future__ import annotations

import ast

from repolens.heuristics.mega_files import is_mega_file_excluded
from repolens.heuristics.paths import is_test_source
from repolens.heuristics.polyglot import OTHER_SUFFIXES, boolean_hits
from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

_PYTHON = {".py"}


def _annotation_is_bool(node: ast.AST | None) -> bool:
    if node is None:
        return False
    if isinstance(node, ast.Name):
        return node.id == "bool"
    if isinstance(node, ast.Attribute):
        return node.attr == "bool"
    if isinstance(node, ast.BinOp):
        return _annotation_is_bool(node.left) or _annotation_is_bool(node.right)
    if isinstance(node, ast.Subscript):
        return _annotation_is_bool(node.value)
    return False


def _is_bool_constant(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, bool)


def _bool_parameters(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    args = func.args
    positional = list(args.posonlyargs) + list(args.args)
    defaults = list(args.defaults)
    pad = len(positional) - len(defaults)
    default_for: dict[str, ast.AST] = {}
    for index, arg in enumerate(positional):
        default_index = index - pad
        if default_index >= 0:
            default_for[arg.arg] = defaults[default_index]
    for index, arg in enumerate(args.kwonlyargs):
        if index < len(args.kw_defaults) and args.kw_defaults[index] is not None:
            default_for[arg.arg] = args.kw_defaults[index]
    names: list[str] = []
    for arg in positional + list(args.kwonlyargs):
        if arg.arg in {"self", "cls"}:
            continue
        if _annotation_is_bool(arg.annotation) or _is_bool_constant(default_for.get(arg.arg)):
            names.append(arg.arg)
    return names


def _test_is_name(test: ast.AST, name: str) -> bool:
    if isinstance(test, ast.Name):
        return test.id == name
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return _test_is_name(test.operand, name)
    return False


def _branches_on(func: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> bool:
    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.found = False

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            return

        def visit_If(self, node: ast.If) -> None:
            if _test_is_name(node.test, name):
                self.found = True
            self.generic_visit(node)

    visitor = _Visitor()
    for stmt in func.body:
        visitor.visit(stmt)
    return visitor.found


def _issue(relative: str, lineno: int, name: str) -> Issue:
    return Issue(
        severity=Severity.LOW,
        priority="P3",
        category="heuristic.boolean_flag",
        file=relative,
        line=max(lineno, 1),
        title=f"Boolean flag {name!r} selects a second behavior",
        explanation=(
            f"{relative}:{lineno} parameter {name!r} is a bool and the function "
            "branches on it. The two branches are two jobs."
        ),
        recommendedFix=f"Split the {name!r} branch into its own function.",
        fixTiming="if time permits",
        source="heuristic",
    )


def find_boolean_flags(files: list[FileEntry]) -> list[Issue]:
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
        if suffix in OTHER_SUFFIXES:
            for lineno, name in boolean_hits(source, suffix):
                issues.append(_issue(entry.relative, lineno, name))
            continue
        if suffix not in _PYTHON:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for name in _bool_parameters(node):
                if _branches_on(node, name):
                    issues.append(_issue(entry.relative, node.lineno, name))
    issues.sort(key=lambda item: (item.file, item.line, item.category, item.title))
    return issues
