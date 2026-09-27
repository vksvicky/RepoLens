# src/repolens/complexity/__init__.py
"""Fast Brain cyclomatic + cognitive complexity (MVP: Python stdlib ast)."""

from __future__ import annotations

from repolens.complexity.thresholds import (
    ComplexityBand,
    band_for_scores,
    should_emit_issue,
)
from repolens.complexity.types import FunctionComplexity

__all__ = [
    "ComplexityBand",
    "FunctionComplexity",
    "band_for_scores",
    "should_emit_issue",
    "run_complexity",
]


def __getattr__(name: str):
    if name == "run_complexity":
        from repolens.complexity.runner import run_complexity

        return run_complexity
    raise AttributeError(name)
