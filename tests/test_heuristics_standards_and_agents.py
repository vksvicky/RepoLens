"""Unit and boundary tests for standards_gaps and agent_context_hygiene heuristics."""

from __future__ import annotations

from pathlib import Path

from repolens.heuristics.agent_context_hygiene import (
    MAX_AGENT_FILE_LINES,
    find_agent_context_hygiene,
)
from repolens.heuristics.standards_gaps import find_standards_gaps
from repolens.inventory import FileEntry
from repolens.schema import Severity


def _entry(path: Path, relative: str) -> FileEntry:
    return FileEntry(
        path=path,
        relative=relative,
        size=path.stat().st_size if path.is_file() else 0,
        priority_band=3,
    )


# ---------------------------------------------------------------------------
# Tests: heuristic.standards_gaps
# ---------------------------------------------------------------------------


def test_standards_gaps_emits_issue_when_no_linter_exists(tmp_path: Path) -> None:
    """When a language has >= 3 source files without any linter config, flag it."""
    src = tmp_path / "src"
    src.mkdir()
    for i in range(3):
        (src / f"app_{i}.py").write_text(f"x = {i}\n", encoding="utf-8")

    entries = [_entry(src / f"app_{i}.py", f"src/app_{i}.py") for i in range(3)]
    issues = find_standards_gaps(tmp_path, entries)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "heuristic.standards_gaps"
    assert "Python" in issue.title
    assert "Ruff" in issue.explanation or "Flake8" in issue.explanation


def test_standards_gaps_suppressed_when_ruff_or_pyproject_configured(tmp_path: Path) -> None:
    """When pyproject.toml contains a [tool.ruff] section, standards gap is cleared."""
    src = tmp_path / "src"
    src.mkdir()
    for i in range(3):
        (src / f"app_{i}.py").write_text(f"x = {i}\n", encoding="utf-8")

    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n", encoding="utf-8")

    entries = [_entry(src / f"app_{i}.py", f"src/app_{i}.py") for i in range(3)]
    issues = find_standards_gaps(tmp_path, entries)
    assert issues == []


def test_standards_gaps_javascript_eslint_detected(tmp_path: Path) -> None:
    """JS repo with eslint config does not trigger standards gap."""
    for i in range(4):
        (tmp_path / f"index_{i}.ts").write_text(f"const a = {i};", encoding="utf-8")
    (tmp_path / "eslint.config.js").write_text("export default [];", encoding="utf-8")

    entries = [_entry(tmp_path / f"index_{i}.ts", f"index_{i}.ts") for i in range(4)]
    issues = find_standards_gaps(tmp_path, entries)
    assert issues == []


# ---------------------------------------------------------------------------
# Tests: heuristic.agent_context_hygiene
# ---------------------------------------------------------------------------


def test_agent_context_hygiene_flags_hardcoded_secrets(tmp_path: Path) -> None:
    """Flag API tokens or secrets placed inside AGENTS.md."""
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(
        "# AGENTS.md\n"
        "Here are project instructions.\n"
        "GITHUB_TOKEN='ghp_123456789012345678901234567890123456'\n",
        encoding="utf-8",
    )
    entry = _entry(agents_md, "AGENTS.md")

    issues = find_agent_context_hygiene([entry])
    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "heuristic.agent_context_hygiene"
    assert issue.severity == Severity.HIGH
    assert "secret" in issue.title.lower() or "token" in issue.title.lower()


def test_agent_context_hygiene_flags_extreme_bloat(tmp_path: Path) -> None:
    """Flag agent instruction files that exceed MAX_AGENT_FILE_LINES."""
    claude_md = tmp_path / "CLAUDE.md"
    body = "\n".join(f"rule {i}" for i in range(MAX_AGENT_FILE_LINES + 20)) + "\n"
    claude_md.write_text(body, encoding="utf-8")
    entry = _entry(claude_md, "CLAUDE.md")

    issues = find_agent_context_hygiene([entry])
    assert len(issues) == 1
    issue = issues[0]
    assert issue.category == "heuristic.agent_context_hygiene"
    assert issue.severity == Severity.LOW
    assert "size" in issue.title.lower() or "limit" in issue.title.lower()


def test_agent_context_hygiene_clean_file(tmp_path: Path) -> None:
    """Clean, concise AGENTS.md passes cleanly."""
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text(
        "# AGENTS.md\n"
        "## Setup\n"
        "Run `pytest` to test.\n",
        encoding="utf-8",
    )
    entry = _entry(agents_md, "AGENTS.md")
    assert find_agent_context_hygiene([entry]) == []
