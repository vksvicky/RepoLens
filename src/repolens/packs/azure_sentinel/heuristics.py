"""Light deterministic checks for Azure Sentinel / Logic Apps packs."""

from __future__ import annotations

import re
from pathlib import Path

from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

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


def _issue(
    *,
    title: str,
    file: str,
    line: int,
    explanation: str,
    severity: Severity,
    fix: str,
    example: str,
) -> Issue:
    kwargs: dict = dict(
        severity=severity,
        priority="P1" if severity in {Severity.CRITICAL, Severity.HIGH} else "P2",
        category="pack.azure_sentinel",
        file=file,
        line=max(line, 1),
        title=title,
        explanation=explanation,
        recommendedFix=fix,
        codeExample=example,
        source="heuristic",
        fixTiming="before launch",
    )
    if severity in {Severity.CRITICAL, Severity.HIGH}:
        kwargs["impact"] = (
            "Hardcoded credentials or identifiers in automation can enable "
            "lateral movement or lock playbooks to the wrong tenant."
        )
    return Issue(**kwargs)


def _line_of(text: str, start: int) -> int:
    return text.count("\n", 0, start) + 1


def scan_azure_sentinel(root: Path, entries: list[FileEntry]) -> list[Issue]:
    """Scan inventory entries for common Sentinel / Logic Apps smells."""
    issues: list[Issue] = []
    for entry in entries:
        if Path(entry.relative).suffix.lower() not in _SUFFIXES:
            # Also accept ARM template names without suffix quirks
            name = Path(entry.relative).name.lower()
            if not any(
                x in name
                for x in ("logic", "sentinel", "playbook", "workflow", "connection")
            ):
                continue
        path = entry.path
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > _MAX_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for match in _TENANT.finditer(text):
            issues.append(
                _issue(
                    title="Hardcoded Azure tenant ID in automation",
                    file=entry.relative,
                    line=_line_of(text, match.start()),
                    explanation=(
                        f"Found literal tenant id `{match.group(2)}`. Prefer parameters, "
                        "Key Vault references, or environment-specific config."
                    ),
                    severity=Severity.MEDIUM,
                    fix="Parameterise tenantId; inject per environment.",
                    example=(
                        '# bicep\nparam tenantId string\n'
                        '# or Key Vault reference — do not commit a fixed GUID'
                    ),
                )
            )
        for match in _SUBSCRIPTION.finditer(text):
            issues.append(
                _issue(
                    title="Hardcoded Azure subscription ID in automation",
                    file=entry.relative,
                    line=_line_of(text, match.start()),
                    explanation=(
                        f"Found literal subscription id `{match.group(2)}`. "
                        "SOAR playbooks should take subscription as a parameter."
                    ),
                    severity=Severity.MEDIUM,
                    fix="Parameterise subscriptionId per environment.",
                    example="param subscriptionId string",
                )
            )
        for match in _SECRET.finditer(text):
            issues.append(
                _issue(
                    title="Connector or workflow secret embedded in definition",
                    file=entry.relative,
                    line=_line_of(text, match.start()),
                    explanation=(
                        f"Found `{match.group(1)}` with an embedded secret value. "
                        "Use Key Vault, managed identity, or secure parameters."
                    ),
                    severity=Severity.HIGH,
                    fix="Remove the secret; use Key Vault or MSI authentication.",
                    example=(
                        '// Prefer managed identity / Key Vault reference\n'
                        '// "authentication": { "type": "ManagedServiceIdentity" }'
                    ),
                )
            )
    return issues
