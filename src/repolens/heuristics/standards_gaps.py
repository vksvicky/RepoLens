"""Missing linter, formatter, or code standards configuration when code files exist.

Detects codebases lacking automated machine-enforceable styling, formatting, or linting.
Covers Python, JavaScript/TypeScript, Go, Rust, Java, and PHP.
"""

from __future__ import annotations

from pathlib import Path

from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

# Ecosystem mapping: (file extensions, configuration files that count as automated standards)
_STANDARDS_BY_ECOSYSTEM: dict[str, tuple[frozenset[str], frozenset[str], str]] = {
    "python": (
        frozenset({".py", ".pyi"}),
        frozenset(
            {
                "ruff.toml",
                ".ruff.toml",
                ".flake8",
                ".pylintrc",
                "setup.cfg",
                ".isort.cfg",
                "pyproject.toml",  # Checked further for tool configs
            }
        ),
        "Ruff / Flake8 / Black",
    ),
    "javascript/typescript": (
        frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}),
        frozenset(
            {
                ".eslintrc",
                ".eslintrc.js",
                ".eslintrc.cjs",
                ".eslintrc.json",
                ".eslintrc.yaml",
                ".eslintrc.yml",
                "eslint.config.js",
                "eslint.config.mjs",
                "eslint.config.cjs",
                "eslint.config.ts",
                ".prettierrc",
                ".prettierrc.json",
                ".prettierrc.yml",
                ".prettierrc.yaml",
                ".prettierrc.js",
                "prettier.config.js",
                "prettier.config.mjs",
                "biome.json",
                "biome.jsonc",
            }
        ),
        "ESLint / Biome / Prettier",
    ),
    "rust": (
        frozenset({".rs"}),
        frozenset({"rustfmt.toml", ".rustfmt.toml", "clippy.toml", ".clippy.toml"}),
        "rustfmt / clippy",
    ),
    "go": (
        frozenset({".go"}),
        frozenset({".golangci.yml", ".golangci.yaml", ".golangci.toml", ".golangci.json"}),
        "golangci-lint",
    ),
}

_PYTHON_LINTER_SECTIONS = (
    "[tool.ruff]",
    "[tool.black]",
    "[tool.flake8]",
    "[tool.pylint]",
    "[tool.isort]",
)


def _pyproject_has_linter(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(section in text for section in _PYTHON_LINTER_SECTIONS)


def find_standards_gaps(root: Path, entries: list[FileEntry]) -> list[Issue]:
    """Flag languages present with substantial code but no automated linter/formatter config."""
    issues: list[Issue] = []

    # Count files per ecosystem
    counts: dict[str, list[str]] = {eco: [] for eco in _STANDARDS_BY_ECOSYSTEM}
    for e in entries:
        ext = Path(e.relative).suffix.lower()
        for eco, (extensions, _, _) in _STANDARDS_BY_ECOSYSTEM.items():
            if ext in extensions:
                counts[eco].append(e.relative)

    for eco, (_extensions, configs, tool_name) in _STANDARDS_BY_ECOSYSTEM.items():
        sample_files = counts[eco]
        # Only flag if there are at least 3 source files in that language
        if len(sample_files) < 3:
            continue

        has_config = False
        for cfg in configs:
            cfg_path = root / cfg
            if cfg_path.is_file():
                if cfg == "pyproject.toml":
                    if _pyproject_has_linter(cfg_path):
                        has_config = True
                        break
                else:
                    has_config = True
                    break

        if not has_config:
            sample = sample_files[0]
            issues.append(
                Issue(
                    severity=Severity.LOW,
                    priority="P3",
                    category="heuristic.standards_gaps",
                    file=sample,
                    line=1,
                    title=f"Missing code standards or linter configuration for {eco.capitalize()}",
                    explanation=(
                        f"{len(sample_files)} {eco} files found (e.g. {sample}) but no automated "
                        f"linter/formatter configuration ({tool_name}) was detected."
                    ),
                    recommendedFix=(
                        f"Add automated standards configuration (e.g. {tool_name}) to maintain "
                        "consistent formatting and prevent styling debates in code reviews."
                    ),
                    fixTiming="if time permits",
                )
            )

    return issues
