"""Line-span explain: the function's own steps, with no model call."""

from __future__ import annotations

import ast
from pathlib import Path

_LABEL_CHARS = 80
_STEP_CAP = 12


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return "call"


def _one_line(text: str) -> str:
    line = " ".join(text.split())
    if len(line) > _LABEL_CHARS:
        return line[: _LABEL_CHARS - 3] + "..."
    return line


def _step_label(stmt: ast.stmt) -> str | None:
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return None
    if isinstance(stmt, ast.If):
        return "if " + _one_line(ast.unparse(stmt.test))
    if isinstance(stmt, ast.For):
        return "for " + _one_line(ast.unparse(stmt.target))
    if isinstance(stmt, ast.With):
        return "with " + _one_line(ast.unparse(stmt.items[0].context_expr))
    if isinstance(stmt, ast.Return):
        shown = _one_line(ast.unparse(stmt.value)) if stmt.value else ""
        return f"return {shown}".rstrip()
    if isinstance(stmt, ast.FunctionDef):
        return f"nested {stmt.name}()"
    if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
        target = _one_line(ast.unparse(stmt.targets[0]))
        return f"{target} = {_call_name(stmt.value)}()"
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return f"{_call_name(stmt.value)}()"
    return _one_line(ast.unparse(stmt))


def _contains(node: ast.AST, line: int) -> bool:
    end = int(getattr(node, "end_lineno", None) or node.lineno)
    return node.lineno <= line <= end


def _function_covering(text: str, line: int):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    exact = None
    container = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.lineno == line:
            exact = node
        if _contains(node, line) and (container is None or node.lineno >= container.lineno):
            container = node
    return exact or container


def large_function_diagram(name: str, span: int, steps: list[str], *, limit: int) -> str:
    """ASCII of the function's own steps. A file move does not change the span."""
    if span < limit:
        head = f"`{name}` is {span} lines, under the {limit}-line span."
    else:
        head = f"`{name}` is {span} lines. The span check flags a function at {limit} lines."
    lines = [
        head,
        "The count is this function. Moving the whole function into another file "
        "leaves the span unchanged.",
        "",
        name,
    ]
    shown = steps[:_STEP_CAP]
    more = len(steps) - len(shown)
    for index, step in enumerate(shown):
        last = index == len(shown) - 1 and more == 0
        mark = "└─" if last else "├─"
        lines.append(f"  {mark} {step}")
    if more:
        lines.append(f"  └─ {more} more steps")
    return "\n".join(lines)


def large_function_doc(root: Path, issue):
    """Explain a line-span finding from the file. None when the function is missing."""
    from repolens.explain_prompt import ExplainDoc, ExplainSolution, _safe_issue_path
    from repolens.heuristics.large_functions import MIN_FUNCTION_LINES

    path = _safe_issue_path(root, issue.file)
    if path is None or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    function = _function_covering(text, issue.line)
    if function is None:
        return None
    end = int(function.end_lineno or function.lineno)
    span = end - function.lineno + 1
    steps = [label for stmt in function.body if (label := _step_label(stmt))]
    diagram = large_function_diagram(function.name, span, steps, limit=MIN_FUNCTION_LINES)
    if span < MIN_FUNCTION_LINES:
        problem = (
            f"`{function.name}` is {span} lines, under the {MIN_FUNCTION_LINES}-line span. "
            "The saved finding was recorded against an older copy of this file."
        )
    else:
        problem = (
            f"`{function.name}` spans {span} lines, from line {function.lineno}. "
            "The check counts the function. Moving that whole function into another "
            "file leaves the span unchanged."
        )
    return ExplainDoc(
        problem=problem,
        impact=issue.impact
        or "A long function is harder to read and to test one step at a time.",
        solutions=[
            ExplainSolution(
                title="Extract one step into a helper in this same file",
                tradeoffs=(
                    "The span shrinks only when that step leaves this function. "
                    "A new file that still contains the whole function stays flagged."
                ),
                impactEffort="Low effort",
            )
        ],
        diagramText=diagram,
        nextStep=(
            f"Extract one step of `{function.name}` into a helper in `{issue.file}`. "
            "Do not move the whole function into a new file."
        ),
    )
