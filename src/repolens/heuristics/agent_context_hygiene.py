"""Agent instruction context hygiene (AGENTS.md, CLAUDE.md, .cursorrules).

Audits persistent agent rule files for:
1. Hardcoded secrets / passwords / bearer tokens.
2. Context bloat (> 500 lines or > 15KB), which causes degradation in agent reasoning.
"""

from __future__ import annotations

import re

from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

_AGENT_FILE_NAMES = frozenset(
    {
        "agents.md",
        "claude.md",
        ".cursorrules",
        ".windsurfrules",
    }
)

_SECRET_PATTERN = re.compile(
    r"(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}|sk-[A-Za-z0-9]{48}|"
    r"bearer\s+[A-Za-z0-9_\-\.]{20,}|(?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{8,}['\"])",
    re.IGNORECASE,
)

MAX_AGENT_FILE_LINES = 500
MAX_AGENT_FILE_BYTES = 15_000


def find_agent_context_hygiene(entries: list[FileEntry]) -> list[Issue]:
    """Audit agent instruction files for secrets or excessive token bloat."""
    issues: list[Issue] = []

    for entry in entries:
        path = entry.path
        name = path.name.lower()
        is_cursor_rule = entry.relative.lower().startswith(".cursor/rules/")
        if name not in _AGENT_FILE_NAMES and not is_cursor_rule:
            continue

        if not path.is_file():
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = text.splitlines()

        # 1. Leaked secret / token in agent instructions
        if _SECRET_PATTERN.search(text):
            issues.append(
                Issue(
                    severity=Severity.HIGH,
                    priority="P1",
                    category="heuristic.agent_context_hygiene",
                    file=entry.relative,
                    line=1,
                    title="Exposed secret or API token in agent instructions",
                    explanation=(
                        f"{entry.relative} appears to contain a hardcoded credential or token. "
                        "Agent context files are committed and sent in LLM context windows."
                    ),
                    recommendedFix=(
                        "Remove the secret from the agent context file immediately, rotate it, "
                        "and instruct agents to read credentials from environment variables."
                    ),
                    impact="Unauthorized access or compromise of repository and API services.",
                    codeExample="export GITHUB_TOKEN=\"$ENV_TOKEN\"",
                    fixTiming="immediately",
                )
            )

        # 2. Extreme context bloat
        if len(lines) > MAX_AGENT_FILE_LINES or entry.size > MAX_AGENT_FILE_BYTES:
            issues.append(
                Issue(
                    severity=Severity.LOW,
                    priority="P3",
                    category="heuristic.agent_context_hygiene",
                    file=entry.relative,
                    line=1,
                    title="Agent instruction file exceeds recommended size limit",
                    explanation=(
                        f"{entry.relative} is {len(lines)} lines ({entry.size} bytes). "
                        "Large prompt context files increase token costs and cause LLM "
                        "attention degradation."
                    ),
                    recommendedFix=(
                        "Compact the agent rules. Remove documentation already in "
                        "README/manifests, and keep only critical non-obvious architecture "
                        "constraints."
                    ),
                    fixTiming="if time permits",
                )
            )

    return issues
