"""Light fintech overlay heuristics (not a PCI certification)."""

from __future__ import annotations

import re
from pathlib import Path

from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

_PAN_HINT = re.compile(
    r"(?i)\b(pan|primary[_-]?account[_-]?number|card[_-]?number)\b.*=.*\d{12,19}"
)
_CLEAR_LOG = re.compile(
    r"(?i)(log|logger|print)\.(debug|info|warning|error|warn)?\s*\(.*\b(pan|cvv|card)\b"
)


def scan_fintech(root: Path, entries: list[FileEntry]) -> list[Issue]:
    issues: list[Issue] = []
    for entry in entries:
        rel = entry.relative.replace("\\", "/")
        if not rel.endswith((".py", ".ts", ".js", ".go")):
            continue
        try:
            text = entry.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if _PAN_HINT.search(line) or _CLEAR_LOG.search(line):
                issues.append(
                    Issue(
                        severity=Severity.HIGH,
                        priority="P1",
                        category="fintech.pci_pan",
                        file=rel,
                        line=i,
                        title="Possible card data in source / logs",
                        explanation=(
                            "Line looks like PAN or card data assignment/logging. "
                            "Not a PCI finding — verify with your QSA tools."
                        ),
                        impact="Card data exposure risk if real PAN reaches logs or git.",
                        recommendedFix=(
                            "Tokenize / mask; never log PAN/CVV; use vault/HSM for keys."
                        ),
                        codeExample=(
                            "# Before\nlog.info('pan=%s', pan)\n\n"
                            "# After\nlog.info('pan=%s', mask_pan(pan))"
                        ),
                        source="heuristic",
                    )
                )
                break
    return issues
