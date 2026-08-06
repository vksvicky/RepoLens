"""Deterministic location Verification & Anchor (Phase 6.4)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AnchorLocation:
    """Resolved physical location inside a repository file."""

    relative: str
    start_line: int
    end_line: int
    start_column: int = 1
    end_column: int | None = None
    quote: str = ""


def _safe_file(root: Path, relative: str) -> Path | None:
    rel = relative.replace("\\", "/").lstrip("./")
    if not rel or ".." in Path(rel).parts:
        return None
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path


def resolve_anchor(
    root: Path,
    relative: str,
    quote: str,
    *,
    hint_line: int | None = None,
) -> AnchorLocation | None:
    """Find ``quote`` in ``relative`` and return its line/column.

    Prefers the occurrence nearest to ``hint_line`` when provided.
    Returns None when the file is missing or the quote is not found.
    """
    needle = (quote or "").strip()
    if not needle:
        return None
    path = _safe_file(root, relative)
    if path is None:
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    matches: list[AnchorLocation] = []
    # Search line-by-line first (typical single-line anchors)
    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        col = line.find(needle)
        if col < 0:
            continue
        matches.append(
            AnchorLocation(
                relative=relative.replace("\\", "/").lstrip("./"),
                start_line=idx,
                end_line=idx,
                start_column=col + 1,
                end_column=col + 1 + len(needle),
                quote=needle,
            )
        )

    if not matches:
        # Multi-line / cross-line: search full text
        pos = text.find(needle)
        if pos < 0:
            return None
        before = text[:pos]
        start_line = before.count("\n") + 1
        line_start = before.rfind("\n") + 1
        start_col = pos - line_start + 1
        end_pos = pos + len(needle)
        end_before = text[:end_pos]
        end_line = end_before.count("\n") + 1
        return AnchorLocation(
            relative=relative.replace("\\", "/").lstrip("./"),
            start_line=start_line,
            end_line=end_line,
            start_column=start_col,
            end_column=None,
            quote=needle,
        )

    if hint_line is None or hint_line < 1:
        return matches[0]
    return min(matches, key=lambda m: abs(m.start_line - hint_line))
