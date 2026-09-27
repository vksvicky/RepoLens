# src/repolens/complexity/runner.py
"""Fast Brain complexity orchestration — Issues + Top-10 scorecard block (B6)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from repolens.complexity.python_ast import analyse_python_source
from repolens.complexity.thresholds import band_for_scores, should_emit_issue
from repolens.complexity.types import FunctionComplexity
from repolens.inventory import FileEntry
from repolens.schema import (
    ComplexityBlock,
    ComplexityHotspot,
    Issue,
    Severity,
)

COMPLEXITY_CATEGORY = "quality.complexity"
_HOTSPOT_LIMIT = 10


@dataclass
class ComplexityResult:
    issues: list[Issue] = field(default_factory=list)
    block: ComplexityBlock = field(default_factory=ComplexityBlock)
    functions: list[FunctionComplexity] = field(default_factory=list)


def _percentile_nearest(sorted_vals: list[int], pct: float) -> int:
    if not sorted_vals:
        return 0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    # Nearest-rank: index = ceil(pct/100 * n) - 1
    import math

    k = max(1, math.ceil(pct / 100.0 * len(sorted_vals)))
    return sorted_vals[min(k - 1, len(sorted_vals) - 1)]


def _is_python(entry: FileEntry) -> bool:
    return entry.relative.replace("\\", "/").endswith(".py")


def _issue_for(func: FunctionComplexity) -> Issue | None:
    band = band_for_scores(cyclomatic=func.cyclomatic, cognitive=func.cognitive)
    if not should_emit_issue(band) or band.severity is None or band.priority is None:
        return None
    severity = band.severity
    priority = band.priority  # type: ignore[assignment]
    impact = ""
    code = ""
    if severity in {Severity.CRITICAL, Severity.HIGH}:
        impact = (
            f"Cyclomatic {func.cyclomatic} / cognitive {func.cognitive} "
            "raises change and defect risk in this function."
        )
        code = (
            f"# Simplify `{func.name}` ({func.path}:{func.start_line})\n"
            f"# cyclomatic={func.cyclomatic} cognitive={func.cognitive}\n"
            "# Prefer guard clauses, extract helpers, reduce nesting.\n"
        )
    return Issue(
        severity=severity,
        priority=priority,
        category=COMPLEXITY_CATEGORY,
        file=func.path,
        line=func.start_line,
        title=(
            f"High complexity: `{func.name}` "
            f"(cyclo={func.cyclomatic}, cognitive={func.cognitive})"
        ),
        explanation=(
            f"Function `{func.name}` spans lines {func.start_line}–{func.end_line} "
            f"with cyclomatic complexity {func.cyclomatic} and cognitive complexity "
            f"{func.cognitive}. "
            + (
                "Both metrics exceed clean thresholds."
                if band.cyclo_triggered and band.cognitive_triggered
                else (
                    "Cyclomatic threshold exceeded."
                    if band.cyclo_triggered
                    else "Cognitive threshold exceeded."
                )
            )
        ),
        impact=impact,
        recommendedFix=(
            "Reduce branching and nesting: extract helpers, replace deep "
            "conditionals with early returns or table-driven logic, then re-measure."
        ),
        codeExample=code,
        fixTiming=(
            "before launch"
            if severity in {Severity.CRITICAL, Severity.HIGH}
            else "if time permits"
        ),
        source="heuristic",
    )


def run_complexity(
    root: Path,
    entries: Sequence[FileEntry],
    *,
    enabled: bool = True,
    hotspot_limit: int = _HOTSPOT_LIMIT,
) -> ComplexityResult:
    """Analyse Python files; emit Issues above thresholds; build Top-N block."""
    if not enabled:
        return ComplexityResult()

    root = root.resolve()
    functions: list[FunctionComplexity] = []
    notes: list[str] = []

    for entry in entries:
        if not _is_python(entry):
            continue
        try:
            text = entry.path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            notes.append(f"skipped {entry.relative}: {exc}"[:200])
            continue
        funcs = analyse_python_source(text, path=entry.relative)
        functions.extend(funcs)

    issues: list[Issue] = []
    for func in functions:
        issue = _issue_for(func)
        if issue is not None:
            issues.append(issue)

    issues.sort(key=lambda i: (i.file, i.line, i.title))

    ranked = sorted(
        functions,
        key=lambda f: (f.cognitive, f.cyclomatic, f.span_lines),
        reverse=True,
    )
    limit = max(0, int(hotspot_limit))
    hotspots = [
        ComplexityHotspot(
            file=f.path,
            function=f.name,
            line=f.start_line,
            cyclomatic=f.cyclomatic,
            cognitive=f.cognitive,
        )
        for f in ranked[:limit]
    ]

    cyclo_vals = sorted(f.cyclomatic for f in functions)
    cog_vals = sorted(f.cognitive for f in functions)

    block = ComplexityBlock(
        functionsAnalysed=len(functions),
        issueCount=len(issues),
        maxCyclomatic=max(cyclo_vals) if cyclo_vals else 0,
        maxCognitive=max(cog_vals) if cog_vals else 0,
        p95Cyclomatic=_percentile_nearest(cyclo_vals, 95),
        p95Cognitive=_percentile_nearest(cog_vals, 95),
        hotspots=hotspots,
        notes=notes,
    )
    return ComplexityResult(issues=issues, block=block, functions=functions)
