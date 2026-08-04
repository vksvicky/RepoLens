"""Local preference memory (dismissals / ignore paths)."""

from __future__ import annotations

import tomllib
from pathlib import Path


class LearningMemory:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.path = self.root / ".repolens" / "memory.toml"
        self.dismissed: list[str] = []
        self.ignore_paths: list[str] = []
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        with self.path.open("rb") as fh:
            data = tomllib.load(fh)
        self.dismissed = list(data.get("dismissed") or [])
        self.ignore_paths = list(data.get("ignore_paths") or [])

    def dismiss(self, issue_id: str) -> None:
        if issue_id not in self.dismissed:
            self.dismissed.append(issue_id)

    def add_ignore(self, pattern: str) -> None:
        if pattern not in self.ignore_paths:
            self.ignore_paths.append(pattern)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# RepoLens local learning memory — stays on this machine.", ""]
        if self.dismissed:
            lines.append("dismissed = [")
            for item in self.dismissed:
                lines.append(f'  "{item}",')
            lines.append("]")
            lines.append("")
        if self.ignore_paths:
            lines.append("ignore_paths = [")
            for item in self.ignore_paths:
                lines.append(f'  "{item}",')
            lines.append("]")
            lines.append("")
        self.path.write_text("\n".join(lines), encoding="utf-8")
