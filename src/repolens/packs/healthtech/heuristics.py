"""Light healthtech overlay heuristics (not a HIPAA certification)."""

from __future__ import annotations

import re
from pathlib import Path

from repolens.inventory import FileEntry
from repolens.schema import Issue, Severity

_PHI_LOG = re.compile(
    r"(?i)(log|logger|print)\.(debug|info|warning|error|warn)?\s*\(.*\b("
    r"ssn|mrn|patient[_-]?id|dob|date[_-]?of[_-]?birth|phi)\b"
)
_SSN_ASSIGN = re.compile(r"(?i)\b(ssn|social[_-]?security)\b.*=.*['\"]?\d{3}")


def scan_healthtech(root: Path, entries: list[FileEntry]) -> list[Issue]:
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
            if _PHI_LOG.search(line) or _SSN_ASSIGN.search(line):
                issues.append(
                    Issue(
                        severity=Severity.HIGH,
                        priority="P1",
                        category="healthtech.phi_logging",
                        file=rel,
                        line=i,
                        title="Possible PHI in logs or literals",
                        explanation=(
                            "Line looks like PHI logging or SSN handling. "
                            "Not a HIPAA finding — verify with your assessor tooling."
                        ),
                        impact="PHI exposure in logs can breach minimum-necessary controls.",
                        recommendedFix=(
                            "Redact PHI; use opaque ids; keep audit trails attributable "
                            "without dumping clinical fields."
                        ),
                        codeExample=(
                            "# Before\nlog.info('patient=%s ssn=%s', name, ssn)\n\n"
                            "# After\nlog.info('patient_id=%s', opaque_id)"
                        ),
                        source="heuristic",
                    )
                )
                break
    return issues
