"""Missing Dependabot / CodeQL when package manifests exist."""

from __future__ import annotations

from pathlib import Path

from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

_MANIFEST_NAMES = frozenset(
    {
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "Pipfile.lock",
        "poetry.lock",
        "go.mod",
        "Cargo.toml",
        "Gemfile",
        "composer.json",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
    }
)

_DEPENDABOT_PATHS = (
    ".github/dependabot.yml",
    ".github/dependabot.yaml",
)

_CODEQL_HINTS = (
    ".github/workflows/codeql.yml",
    ".github/workflows/codeql.yaml",
    ".github/workflows/codeql-analysis.yml",
    ".github/workflows/codeql-analysis.yaml",
)


def _has_path(root: Path, relative: str) -> bool:
    return (root / relative).is_file()


def _workflow_mentions_codeql(root: Path) -> bool:
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return False
    for path in workflows.glob("*.y*ml"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        if "codeql" in text or "github/codeql-action" in text:
            return True
    return False


def find_ci_gaps(root: Path, entries: list[FileEntry]) -> list[Issue]:
    manifests = [e.relative for e in entries if Path(e.relative).name in _MANIFEST_NAMES]
    if not manifests:
        # Also detect manifests that may not be in the capped inventory.
        for name in _MANIFEST_NAMES:
            if (root / name).is_file():
                manifests.append(name)
                break
    if not manifests:
        return []

    has_dependabot = any(_has_path(root, p) for p in _DEPENDABOT_PATHS)
    has_codeql = any(_has_path(root, p) for p in _CODEQL_HINTS) or _workflow_mentions_codeql(root)

    if has_dependabot and has_codeql:
        return []

    missing: list[str] = []
    if not has_dependabot:
        missing.append("Dependabot")
    if not has_codeql:
        missing.append("CodeQL")

    sample = manifests[0]
    return [
        Issue(
            severity=Severity.LOW,
            priority="P3",
            category="heuristic.ci_gaps",
            file=sample,
            line=1,
            title=f"Missing {' / '.join(missing)} for dependency ecosystem",
            explanation=(
                f"Package manifest(s) present (e.g. {sample}) but "
                f"{' and '.join(missing)} automation was not found under .github/."
            ),
            recommendedFix=(
                "Add `.github/dependabot.yml` and a CodeQL (or equivalent SCA/SAST) "
                "workflow so dependency and code alerts run continuously."
            ),
            fixTiming="if time permits",
        )
    ]
