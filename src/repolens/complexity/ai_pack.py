# src/repolens/complexity/ai_pack.py
"""C1 — Cap Slow Brain complexity explanations at top_n (default 5, hard max 10)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from repolens.complexity.thresholds import band_for_scores, should_emit_issue
from repolens.complexity.types import FunctionComplexity

_HARD_MAX = 10
_SLICE_CHAR_CAP = 4000


def select_complexity_ai_targets(
    functions: Sequence[FunctionComplexity],
    *,
    top_n: int = 5,
) -> list[FunctionComplexity]:
    """Issue-eligible functions only, worst first, capped at min(top_n, 10)."""
    limit = max(0, min(int(top_n), _HARD_MAX))
    if limit == 0:
        return []
    eligible = [
        f
        for f in functions
        if should_emit_issue(
            band_for_scores(cyclomatic=f.cyclomatic, cognitive=f.cognitive)
        )
    ]
    ranked = sorted(
        eligible,
        key=lambda f: (f.cognitive, f.cyclomatic, f.span_lines),
        reverse=True,
    )
    return ranked[:limit]


def _read_slice(root: Path, func: FunctionComplexity) -> str:
    path = root / func.path
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return f"# (could not read {func.path})"
    start = max(1, func.start_line)
    end = min(len(lines), max(start, func.end_line))
    chunk = "\n".join(lines[start - 1 : end])
    if len(chunk) > _SLICE_CHAR_CAP:
        chunk = chunk[:_SLICE_CHAR_CAP] + "\n# … truncated …"
    return chunk


def format_complexity_ai_section(
    root: Path,
    targets: Sequence[FunctionComplexity],
) -> str:
    """Markdown section appended to Slow Brain prompts for top-N hotspots."""
    if not targets:
        return ""
    lines: list[str] = [
        "## Complexity hotspots for AI explanation (capped)",
        "",
        "Fast Brain already computed cyclomatic and cognitive scores. "
        "**Do not invent metric scores.** For each hotspot below:",
        "- Explain why the function is hard to change/test (concrete control-flow).",
        "- Suggest a best-practice refactor with a short `codeExample` when severity "
        "is HIGH or CRITICAL.",
        "- Do not lecture on textbook theory; file/line evidence only.",
        "",
        f"Targets in this pack: {len(targets)} (hard max {_HARD_MAX}).",
        "",
    ]
    for i, func in enumerate(targets, start=1):
        lines.append(
            f"### {i}. `{func.path}:{func.start_line}` `{func.name}` "
            f"(cyclo={func.cyclomatic}, cognitive={func.cognitive})"
        )
        lines.append("```")
        lines.append(_read_slice(root, func))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)
