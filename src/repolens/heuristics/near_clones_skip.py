"""Import-region and header-comment skip helpers for near-clone windows."""

from __future__ import annotations

from collections.abc import Sequence

# C-family line/block comments: // and /* … */
_C_STYLE_COMMENT_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".kt"}


def is_comment_line(line: str, suffix: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if suffix in {".py", ".pyi"}:
        return stripped.startswith("#")
    if suffix in _C_STYLE_COMMENT_SUFFIXES:
        return (
            stripped.startswith("//")
            or stripped.startswith("*")
            or stripped.startswith("/*")
            or stripped.endswith("*/")
        )
    return stripped.startswith("#") or stripped.startswith("//")


def is_go_import_member(stripped: str) -> bool:
    """True for lines inside a Go ``import ( … )`` group."""
    if stripped in {"(", ")"}:
        return True
    if stripped.startswith('"') and stripped.endswith('"'):
        return True
    if '"' in stripped:
        head, _, tail = stripped.partition(" ")
        path = tail.strip() if tail else ""
        if path.startswith('"') and path.endswith('"'):
            return head == "." or head.isidentifier()
    return False


def is_import_line(line: str, suffix: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if suffix in {".py", ".pyi"}:
        return stripped.startswith("import ") or stripped.startswith("from ")
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        return stripped.startswith("import ") or "require(" in stripped
    if suffix == ".go":
        return stripped.startswith("import ") or stripped.startswith("import(")
    if suffix == ".rs":
        return stripped.startswith("use ") or stripped.startswith("extern crate ")
    if suffix == ".kt":
        return stripped.startswith("import ")
    return False


def py_import_region_mask(raw_lines: Sequence[str]) -> list[bool]:
    """Per physical line: True when the line is part of a ``from``/``import`` statement.

    Tracks parenthesized multi-line import bodies so member-only windows
    (``option_foo,``) are suppressed the same way as single-line imports.
    """
    mask = [False] * len(raw_lines)
    depth = 0
    for i, raw in enumerate(raw_lines):
        stripped = raw.strip()
        if depth > 0:
            mask[i] = True
            depth += stripped.count("(") - stripped.count(")")
            if depth < 0:
                depth = 0
            continue
        if stripped.startswith("from ") or stripped.startswith("import "):
            mask[i] = True
            depth = stripped.count("(") - stripped.count(")")
            if depth < 0:
                depth = 0
    return mask


def window_entirely_in_import_region(
    *,
    phys_start: int,
    phys_end: int,
    raw_lines: Sequence[str],
    import_mask: Sequence[bool],
) -> bool:
    saw_code = False
    for i in range(phys_start, phys_end + 1):
        if i < 1 or i > len(raw_lines):
            continue
        if not raw_lines[i - 1].strip():
            continue
        saw_code = True
        if i - 1 >= len(import_mask) or not import_mask[i - 1]:
            return False
    return saw_code


def chunk_is_import_only(norm_chunk: Sequence[str], suffix: str) -> bool:
    non_blank = [line.strip() for line in norm_chunk if line.strip()]
    if not non_blank:
        return False
    if suffix == ".go":
        # Require an ``import`` keyword so bare string-literal windows are not suppressed.
        has_import = any(
            line.startswith("import ") or line.startswith("import(") or line == "import"
            for line in non_blank
        )
        if not has_import:
            return False
        return all(
            line.startswith("import ")
            or line.startswith("import(")
            or line == "import"
            or is_go_import_member(line)
            for line in non_blank
        )
    return all(is_import_line(line, suffix) for line in non_blank)


def should_skip_window(
    *,
    norm_chunk: Sequence[str],
    phys_start: int,
    phys_end: int,
    raw_lines: Sequence[str],
    suffix: str,
    header_n: int,
    import_mask: Sequence[bool] | None = None,
) -> bool:
    if phys_end <= header_n:
        phys_text = [
            raw_lines[i - 1]
            for i in range(phys_start, phys_end + 1)
            if 1 <= i <= len(raw_lines)
        ]
        if phys_text and all(is_comment_line(line, suffix) for line in phys_text):
            return True
    if import_mask is not None and window_entirely_in_import_region(
        phys_start=phys_start,
        phys_end=phys_end,
        raw_lines=raw_lines,
        import_mask=import_mask,
    ):
        return True
    return chunk_is_import_only(norm_chunk, suffix)
