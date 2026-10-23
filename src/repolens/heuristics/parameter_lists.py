"""Long parameter list heuristic (Fast Brain — AST analysis)."""

from __future__ import annotations

import ast

from repolens.heuristics.mega_files import is_mega_file_excluded
from repolens.heuristics.paths import is_test_source
from repolens.heuristics.polyglot import OTHER_SUFFIXES, parameter_hits
from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

MAX_PARAMETER_COUNT = 6
_PYTHON = {".py"}


def _call_default_names(func: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Parameters whose default is a call, such as a Typer option factory."""
    args = func.args
    positional = list(getattr(args, "posonlyargs", [])) + list(args.args)
    defaults = list(args.defaults)
    pad = len(positional) - len(defaults)
    names: set[str] = set()
    for index, arg in enumerate(positional):
        default_index = index - pad
        if default_index >= 0 and isinstance(defaults[default_index], ast.Call):
            names.add(arg.arg)
    for index, arg in enumerate(args.kwonlyargs):
        if index < len(args.kw_defaults) and isinstance(args.kw_defaults[index], ast.Call):
            names.add(arg.arg)
    return names


def _count_parameters(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count parameters, excluding self/cls, varargs, and call defaults."""
    args = func.args
    injected = _call_default_names(func)
    counted: list[str] = []

    for arg in getattr(args, "posonlyargs", []):
        counted.append(arg.arg)
    for arg in args.args:
        counted.append(arg.arg)
    for arg in args.kwonlyargs:
        counted.append(arg.arg)

    if counted and counted[0] in ("self", "cls"):
        counted = counted[1:]
    return len([name for name in counted if name not in injected])


def _parameter_explanation(relative: str, lineno: int, name: str, count: int) -> str:
    return (
        f"{relative}:{lineno} function {name!r} defines {count} parameters. "
        "A function is flagged at 7 or more, not counting self, cls, *args, or **kwargs."
    )


def _parameter_issue(relative: str, lineno: int, name: str, count: int) -> Issue:
    return Issue(
        severity=Severity.LOW,
        priority="P3",
        category="heuristic.long_parameter_list",
        file=relative,
        line=max(lineno, 1),
        title=f"Function {name!r} has {count} parameters",
        explanation=_parameter_explanation(relative, lineno, name, count),
        recommendedFix=("Group related parameters into a dataclass, TypedDict, or config model."),
        fixTiming="if time permits",
        source="heuristic",
    )


def parameter_list_issues(entry: FileEntry, source: str) -> list[Issue]:
    if is_test_source(entry.relative) or is_mega_file_excluded(entry.relative):
        return []
    suffix = entry.path.suffix.lower()
    if suffix in OTHER_SUFFIXES:
        return [
            _parameter_issue(entry.relative, lineno, name, count)
            for lineno, name, count in parameter_hits(source, suffix)
        ]
    if suffix not in _PYTHON:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    issues: list[Issue] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        param_count = _count_parameters(node)
        if param_count <= MAX_PARAMETER_COUNT:
            continue
        issues.append(_parameter_issue(entry.relative, node.lineno, node.name, param_count))
    return issues


def find_long_parameter_lists(files: list[FileEntry]) -> list[Issue]:
    issues: list[Issue] = []
    for entry in files:
        if not entry.path.is_file():
            continue
        try:
            source = entry.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        issues.extend(parameter_list_issues(entry, source))
    issues.sort(key=lambda i: (i.file, i.line, i.category, i.title))
    return issues
