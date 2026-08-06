"""Lightweight file structure outlines for explain / LLM context (no full AST dump)."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SymbolSpan:
    kind: str  # class | function | async_function
    name: str
    start_line: int
    end_line: int

    @property
    def line_count(self) -> int:
        return max(1, self.end_line - self.start_line + 1)


def _python_symbols(text: str) -> list[SymbolSpan]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out: list[SymbolSpan] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            end = getattr(node, "end_lineno", None) or node.lineno
            out.append(
                SymbolSpan("class", node.name, node.lineno, int(end))
            )
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    cend = getattr(child, "end_lineno", None) or child.lineno
                    kind = (
                        "async_method"
                        if isinstance(child, ast.AsyncFunctionDef)
                        else "method"
                    )
                    out.append(
                        SymbolSpan(
                            kind,
                            f"{node.name}.{child.name}",
                            child.lineno,
                            int(cend),
                        )
                    )
        elif isinstance(node, ast.FunctionDef):
            end = getattr(node, "end_lineno", None) or node.lineno
            out.append(
                SymbolSpan("function", node.name, node.lineno, int(end))
            )
        elif isinstance(node, ast.AsyncFunctionDef):
            end = getattr(node, "end_lineno", None) or node.lineno
            out.append(
                SymbolSpan("async_function", node.name, node.lineno, int(end))
            )
    return out


_GENERIC_DEF_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:function|def|class|fn|func)\s+([A-Za-z_][\w]*)"
)


def _generic_symbols(text: str) -> list[SymbolSpan]:
    """Best-effort for non-Python: line starts that look like defs/classes."""
    out: list[SymbolSpan] = []
    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        m = _GENERIC_DEF_RE.match(line)
        if not m:
            continue
        kind = "class" if "class" in line.split("(")[0] else "function"
        out.append(SymbolSpan(kind, m.group(1), i, i))
    return out


def collect_symbols(path: Path, text: str) -> list[SymbolSpan]:
    if path.suffix.lower() == ".py":
        return _python_symbols(text)
    return _generic_symbols(text)


def format_file_outline(
    path: Path,
    *,
    max_symbols: int = 48,
    min_lines_for_outline: int = 80,
    display_path: str | None = None,
) -> str:
    """Human-readable structure summary for LLM prompts.

    Returns empty string when the file is small or unreadable.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"(could not read file for outline: {exc})"

    total_lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    if total_lines < min_lines_for_outline:
        return ""

    symbols = collect_symbols(path, text)
    if not symbols:
        return (
            f"File has {total_lines} lines but no top-level classes/functions "
            "were detected for an outline."
        )

    # Prefer largest symbols first for mega-file guidance, keep declaration order
    # for the printed list but annotate size.
    ranked = sorted(symbols, key=lambda s: (-s.line_count, s.start_line))
    top = ranked[:max_symbols]
    # Stable display: by start line among selected
    top.sort(key=lambda s: s.start_line)

    label = display_path or path.as_posix()
    lines = [
        f"Structure outline for `{label}` ({total_lines} lines):",
        "Largest / notable symbols (use ONLY these names when suggesting splits):",
    ]
    for sym in top:
        lines.append(
            f"- {sym.kind} `{sym.name}` — lines {sym.start_line}–{sym.end_line} "
            f"({sym.line_count} lines)"
        )
    if len(symbols) > max_symbols:
        lines.append(f"… ({len(symbols) - max_symbols} more symbols omitted)")
    return "\n".join(lines)
