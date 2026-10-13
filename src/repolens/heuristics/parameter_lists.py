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


def _count_parameters(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count parameters, excluding self/cls and varargs (*args, **kwargs)."""
    args = func.args
    counted: list[str] = []

    # Positional-only parameters (Python 3.8+)
    for arg in getattr(args, "posonlyargs", []):
        counted.append(arg.arg)

    # Standard positional / keyword arguments
    for arg in args.args:
        counted.append(arg.arg)

    # Keyword-only arguments
    for arg in args.kwonlyargs:
        counted.append(arg.arg)

    # If the first parameter is 'self' or 'cls', drop it
    if counted and counted[0] in ("self", "cls"):
        counted = counted[1:]

    return len(counted)


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


def find_long_parameter_lists(files: list[FileEntry]) -> list[Issue]:
    issues: list[Issue] = []

    for entry in files:
        if not entry.path.is_file():
            continue
        if is_test_source(entry.relative) or is_mega_file_excluded(entry.relative):
            continue
        suffix = entry.path.suffix.lower()
        if suffix in OTHER_SUFFIXES:
            try:
                source = entry.path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for lineno, name, count in parameter_hits(source, suffix):
                issues.append(_parameter_issue(entry.relative, lineno, name, count))
            continue
        if suffix not in _PYTHON:
            continue

        try:
            source = entry.path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            param_count = _count_parameters(node)
            if param_count > MAX_PARAMETER_COUNT:
                issues.append(
                    Issue(
                        severity=Severity.LOW,
                        priority="P3",
                        category="heuristic.long_parameter_list",
                        file=entry.relative,
                        line=max(node.lineno, 1),
                        title=f"Function {node.name!r} has {param_count} parameters",
                        explanation=_parameter_explanation(
                            entry.relative, node.lineno, node.name, param_count
                        ),
                        recommendedFix=(
                            "Group related parameters into a dataclass, TypedDict, or config model."
                        ),
                        fixTiming="if time permits",
                        source="heuristic",
                    )
                )

    issues.sort(key=lambda i: (i.file, i.line, i.category, i.title))
    return issues
