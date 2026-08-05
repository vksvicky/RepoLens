"""Pipeline result types and errors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from repolens.schema import FindingReport


class ScannerRequirementError(Exception):
    """Raised when --require-scanners is set and a requested tool is missing."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        tools = ", ".join(missing)
        super().__init__(f"Required scanner(s) missing: {tools}. See docs/scanners.md")


@dataclass
class ReviewResult:
    report: FindingReport
    markdown_path: Path | None
    json_path: Path | None
    files_scanned: int
    dry_run: bool
