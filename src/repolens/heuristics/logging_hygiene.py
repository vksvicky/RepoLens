"""Logging hygiene heuristics (eager formatting, sensitive data in logs, swallowed exceptions)."""

from __future__ import annotations

import ast

from repolens.heuristics.mega_files import is_mega_file_excluded
from repolens.heuristics.paths import is_test_source
from repolens.heuristics.polyglot import OTHER_SUFFIXES, logging_hits, name_is_secret
from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

_PYTHON = {".py"}

_LOG_ATTRS = frozenset(
    {"debug", "info", "warning", "warn", "error", "exception", "critical", "fatal", "log"}
)


def _receiver_is_logger(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id in {"log", "logger", "logging", "console"}
    if isinstance(node, ast.Attribute):
        return node.attr in {"log", "logger"} or _receiver_is_logger(node.value)
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "getLogger":
            return True
        if isinstance(func, ast.Name) and func.id == "getLogger":
            return True
    return False


def _is_log_or_print_call(call: ast.Call) -> tuple[bool, str]:
    """Return (is_log_or_print, kind) where kind is 'log', 'logger', or 'print'."""
    func = call.func
    if isinstance(func, ast.Name):
        if func.id == "print":
            return True, "print"
        if func.id in ("log", "logger"):
            return True, func.id
    elif isinstance(func, ast.Attribute) and func.attr in _LOG_ATTRS:
        if _receiver_is_logger(func.value):
            return True, "logger"
    return False, ""


def _is_eager_log_call(call: ast.Call) -> bool:
    """True when a logger call builds its message with an f-string or +."""
    is_log, kind = _is_log_or_print_call(call)
    if not is_log or kind == "print" or not call.args:
        return False
    first_arg = call.args[0]
    if isinstance(first_arg, ast.JoinedStr):
        return True
    return isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, ast.Add)


def _is_empty_or_pass_body(body: list[ast.stmt]) -> bool:
    """Check if except handler body is only pass, ... (Ellipsis), or bare return."""
    if not body:
        return True
    if len(body) == 1:
        stmt = body[0]
        if isinstance(stmt, ast.Pass):
            return True
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            if stmt.value.value is ... or stmt.value.value is Ellipsis:
                return True
        if isinstance(stmt, ast.Return) and (
            stmt.value is None or isinstance(stmt.value, ast.Constant)
        ):
            return True
    return False


def _secret_in_call(call: ast.Call) -> str | None:
    """A credential identifier passed to the call, not a word inside a message."""
    for arg in list(call.args) + [kw.value for kw in call.keywords]:
        for node in ast.walk(arg):
            if isinstance(node, ast.Name) and name_is_secret(node.id):
                return node.id
            if isinstance(node, ast.Attribute) and name_is_secret(node.attr):
                return node.attr
    return None


def _preserves_traceback(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr == "exception":
        return True
    for keyword in call.keywords:
        if keyword.arg != "exc_info":
            continue
        if isinstance(keyword.value, ast.Constant) and keyword.value.value in (False, None):
            return False
        return True
    return False


def _log_call_flags(node: ast.AST) -> tuple[bool, bool]:
    """Return whether this node keeps a traceback, and whether it is a plain log."""
    if not isinstance(node, ast.Call):
        return False, False
    is_log, kind = _is_log_or_print_call(node)
    if not is_log or kind == "print":
        return False, False
    if _preserves_traceback(node):
        return True, False
    return False, True


def _handler_is_swallowed(handler: ast.ExceptHandler) -> bool:
    """Silent handlers, and logs that drop the traceback."""
    has_raise = False
    has_traceback = False
    has_plain_log = False
    nested = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for stmt in handler.body:
        if isinstance(stmt, nested):
            continue
        for node in ast.walk(stmt):
            if isinstance(node, ast.Raise):
                has_raise = True
            keeps, plain = _log_call_flags(node)
            has_traceback = has_traceback or keeps
            has_plain_log = has_plain_log or plain
    if has_raise or has_traceback:
        return False
    if _is_empty_or_pass_body(handler.body):
        return True
    return has_plain_log


def _secret_issue(relative: str, lineno: int, kind: str, secret: str) -> Issue:
    return Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="heuristic.logging_secret",
        file=relative,
        line=max(lineno, 1),
        title=f"Sensitive term {secret!r} in {kind} call",
        explanation=(
            f"{relative}:{lineno} passes {secret!r} into `{kind}`. "
            "The value can land in a log sink."
        ),
        recommendedFix=(f"Redact {secret!r} before the call, or drop the call."),
        fixTiming="before launch",
        source="heuristic",
    )


def _swallowed_issue(relative: str, lineno: int) -> Issue:
    return Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="heuristic.swallowed_exception",
        file=relative,
        line=max(lineno, 1),
        title="Swallowed exception without a traceback",
        explanation=(
            f"{relative}:{lineno} catches an exception and neither re-raises it nor "
            "logs it with logger.exception or exc_info=True."
        ),
        recommendedFix=("Call logger.exception(...) or log with exc_info=True, or re-raise."),
        fixTiming="before launch",
        source="heuristic",
    )


def _eager_issue(relative: str, lineno: int) -> Issue:
    return Issue(
        severity=Severity.LOW,
        priority="P3",
        category="heuristic.logging_eager",
        file=relative,
        line=lineno,
        title="Eager string formatting in log call",
        explanation=(
            f"{relative}:{lineno} builds the log message before the call. "
            "Pass a format string and arguments so a disabled level does no work."
        ),
        recommendedFix="Use the logger's format string and arguments.",
        fixTiming="if time permits",
        source="heuristic",
    )


def _python_eager_issue(relative: str, lineno: int) -> Issue:
    return Issue(
        severity=Severity.LOW,
        priority="P3",
        category="heuristic.logging_eager",
        file=relative,
        line=max(lineno, 1),
        title="Eager string formatting in log call",
        explanation=(
            f"{relative}:{lineno} passes an f-string or concat "
            "to a logger call. Prefer parameterized logging (e.g. "
            "logger.info('user %s', user_id)) to avoid formatting overhead "
            "when the log level is disabled."
        ),
        recommendedFix=(
            "Pass static format strings and positional arguments "
            "(e.g. logger.info('user %s', user_id)) instead of f-strings."
        ),
        fixTiming="if time permits",
        source="heuristic",
    )


def _issues_from_other(relative: str, source: str, suffix: str, *, is_test: bool) -> list[Issue]:
    built: list[Issue] = []
    for category, lineno, detail in logging_hits(source, suffix, is_test=is_test):
        if category == "heuristic.logging_eager":
            built.append(_eager_issue(relative, lineno))
        elif category == "heuristic.logging_secret":
            built.append(_secret_issue(relative, lineno, "log", detail))
        else:
            built.append(_swallowed_issue(relative, lineno))
    return built


def find_logging_hygiene(files: list[FileEntry]) -> list[Issue]:
    issues: list[Issue] = []

    for entry in files:
        if not entry.path.is_file():
            continue
        if is_mega_file_excluded(entry.relative):
            continue
        suffix = entry.path.suffix.lower()
        is_test = is_test_source(entry.relative)
        if suffix in OTHER_SUFFIXES:
            try:
                source = entry.path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            issues.extend(_issues_from_other(entry.relative, source, suffix, is_test=is_test))
            continue
        if suffix not in _PYTHON:
            continue

        try:
            source = entry.path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            continue

        for node in ast.walk(tree):
            # 1. Eager log formatting (runs on production and test files)
            if isinstance(node, ast.Call) and _is_eager_log_call(node):
                issues.append(_python_eager_issue(entry.relative, node.lineno))

            if not is_test and isinstance(node, ast.Call):
                is_call, kind = _is_log_or_print_call(node)
                secret = _secret_in_call(node) if is_call else None
                if secret:
                    issues.append(_secret_issue(entry.relative, node.lineno, kind, secret))

            if not is_test and isinstance(node, ast.ExceptHandler):
                if _handler_is_swallowed(node):
                    issues.append(_swallowed_issue(entry.relative, node.lineno))

    issues.sort(key=lambda i: (i.file, i.line, i.category, i.title))
    return issues
