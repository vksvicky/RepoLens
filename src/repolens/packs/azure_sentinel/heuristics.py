"""Light deterministic checks for Azure Sentinel / Logic Apps packs."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

logger = logging.getLogger(__name__)

_GUID = (
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
# Allow JSON/YAML key quoting: "tenantId": "…"
_TENANT = re.compile(
    rf"""(?i)["']?(tenant[_-]?id|tenantid)["']?\s*[=:]\s*["']?({_GUID})["']?""",
)
_SUBSCRIPTION = re.compile(
    rf"""(?i)["']?(subscription[_-]?id|subscriptionid)["']?\s*[=:]\s*["']?({_GUID})["']?""",
)
_SECRET = re.compile(
    r"""(?i)["']?(client[_-]?secret|shared[_-]?key|primary[_-]?key|password)["']?\s*[=:]\s*["']([^"']{8,})["']""",
)

_SUFFIXES = frozenset(
    {
        ".json",
        ".bicep",
        ".arm",
        ".yml",
        ".yaml",
        ".xml",
        ".txt",
    }
)
_MAX_BYTES = 400_000


@dataclass(frozen=True)
class _PackFinding:
    title: str
    file: str
    line: int
    explanation: str
    severity: Severity
    fix: str
    example: str


def _issue(hit: _PackFinding) -> Issue:
    kwargs: dict = dict(
        severity=hit.severity,
        priority="P1" if hit.severity in {Severity.CRITICAL, Severity.HIGH} else "P2",
        category="pack.azure_sentinel",
        file=hit.file,
        line=max(hit.line, 1),
        title=hit.title,
        explanation=hit.explanation,
        recommendedFix=hit.fix,
        codeExample=hit.example,
        source="heuristic",
        fixTiming="before launch",
    )
    if hit.severity in {Severity.CRITICAL, Severity.HIGH}:
        kwargs["impact"] = (
            "Hardcoded credentials or identifiers in automation can enable "
            "lateral movement or lock playbooks to the wrong tenant."
        )
    return Issue(**kwargs)


def _line_of(text: str, start: int) -> int:
    return text.count("\n", 0, start) + 1


_CAPTURED_ID = 2
_TENANT_EXAMPLE = (
    "# bicep\nparam tenantId string\n"
    "# or Key Vault reference — do not commit a fixed GUID"
)
_SECRET_EXAMPLE = (
    "// Prefer managed identity / Key Vault reference\n"
    '// "authentication": { "type": "ManagedServiceIdentity" }'
)
_NAME_HINTS = ("logic", "sentinel", "playbook", "workflow", "connection")


def _entry_text(entry: FileEntry) -> str | None:
    name = Path(entry.relative).name.lower()
    suffix = Path(entry.relative).suffix.lower()
    if suffix not in _SUFFIXES and not any(hint in name for hint in _NAME_HINTS):
        return None
    path = entry.path
    if not path.is_file():
        return None
    try:
        if path.stat().st_size > _MAX_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.debug("unreadable azure pack file %s", path, exc_info=True)
        return None


def _tenant_issues(relative: str, text: str) -> list[Issue]:
    found: list[Issue] = []
    for match in _TENANT.finditer(text):
        guid = match.group(_CAPTURED_ID)
        explanation = (
            f"Found literal tenant id `{guid}`. Prefer parameters, "
            "Key Vault references, or environment-specific config."
        )
        found.append(_issue(_PackFinding(
            title="Hardcoded Azure tenant ID in automation",
            file=relative,
            line=_line_of(text, match.start()),
            explanation=explanation,
            severity=Severity.MEDIUM,
            fix="Parameterise tenantId; inject per environment.",
            example=_TENANT_EXAMPLE,
        )))
    return found


def _subscription_issues(relative: str, text: str) -> list[Issue]:
    found: list[Issue] = []
    for match in _SUBSCRIPTION.finditer(text):
        guid = match.group(_CAPTURED_ID)
        explanation = (
            f"Found literal subscription id `{guid}`. "
            "SOAR playbooks should take subscription as a parameter."
        )
        found.append(_issue(_PackFinding(
            title="Hardcoded Azure subscription ID in automation",
            file=relative,
            line=_line_of(text, match.start()),
            explanation=explanation,
            severity=Severity.MEDIUM,
            fix="Parameterise subscriptionId per environment.",
            example="param subscriptionId string",
        )))
    return found


def _secret_issues(relative: str, text: str) -> list[Issue]:
    found: list[Issue] = []
    for match in _SECRET.finditer(text):
        name = match.group(1)
        explanation = (
            f"Found `{name}` with an embedded secret value. "
            "Use Key Vault, managed identity, or secure parameters."
        )
        found.append(_issue(_PackFinding(
            title="Connector or workflow secret embedded in definition",
            file=relative,
            line=_line_of(text, match.start()),
            explanation=explanation,
            severity=Severity.HIGH,
            fix="Remove the secret; use Key Vault or MSI authentication.",
            example=_SECRET_EXAMPLE,
        )))
    return found


def scan_azure_sentinel(root: Path, entries: list[FileEntry]) -> list[Issue]:
    """Scan inventory entries for common Sentinel / Logic Apps smells."""
    issues: list[Issue] = []
    for entry in entries:
        text = _entry_text(entry)
        if text is None:
            continue
        issues.extend(_tenant_issues(entry.relative, text))
        issues.extend(_subscription_issues(entry.relative, text))
        issues.extend(_secret_issues(entry.relative, text))
    return issues
