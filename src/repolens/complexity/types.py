# src/repolens/complexity/types.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FunctionComplexity:
    """One analysed function / method with McCabe + cognitive scores."""

    name: str
    path: str
    start_line: int
    end_line: int
    cyclomatic: int
    cognitive: int
    language: str = "python"

    @property
    def span_lines(self) -> int:
        return max(0, self.end_line - self.start_line + 1)
