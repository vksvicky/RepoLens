"""Parse RepoLens markdown gate reports back into FindingReport (bootstrap)."""

from __future__ import annotations

import re
from pathlib import Path

from repolens.schema import FindingReport, Issue, Severity, Summary

_COUNTS_RE = re.compile(
    r"\*\*Counts:\*\*\s*Critical\s+(\d+)\s*·\s*High\s+(\d+)\s*·\s*"
    r"Medium\s+(\d+)\s*·\s*Low\s+(\d+)",
    re.IGNORECASE,
)
_CONF_RE = re.compile(r"\*\*Gate confidence:\*\*\s*(\d+)%")
_ISSUE_HEAD_RE = re.compile(
    r"^### \[(CRITICAL|HIGH|MEDIUM|LOW)\] (.+)$", re.MULTILINE
)
_FIELD_RE = re.compile(
    r"^- \*\*(Priority|File|Line|Category|Explanation|Impact|"
    r"Recommended fix|Fix timing|OWASP|CWE|Code example):\*\*\s*(.*)$",
    re.MULTILINE,
)
_SKIP_MARKERS = (
    "LLM skipped",
    "no prior LLM snapshot",
    "n/a (LLM skipped",
    "LLM: skipped",
)


def _extract_code_example(block: str) -> str:
    marker = "- **Code example:**"
    idx = block.find(marker)
    if idx < 0:
        return ""
    rest = block[idx + len(marker) :]
    fence_open = re.search(r"`{3,}[^\n]*\n", rest)
    if not fence_open:
        return rest.strip().strip("`")
    after = rest[fence_open.end() :]
    close = re.search(r"\n`{3,}[ \t]*\n?", after)
    if not close:
        return after.strip()
    return after[: close.start()].strip()


def _field_map(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in _FIELD_RE.finditer(block):
        key = match.group(1).strip().lower()
        if key == "code example":
            continue
        val = match.group(2).strip()
        fields[key] = val
    code = _extract_code_example(block)
    if code and not code.startswith("_MISSING"):
        fields["code example"] = code
    return fields


def parse_markdown_report(text: str) -> FindingReport | None:
    """Best-effort parse of a RepoLens markdown report. None if unusable."""
    if any(m in text for m in _SKIP_MARKERS) and "### [" not in text:
        return None

    conf_m = _CONF_RE.search(text)
    confidence = int(conf_m.group(1)) if conf_m else 50

    issues: list[Issue] = []
    heads = list(_ISSUE_HEAD_RE.finditer(text))
    for i, head in enumerate(heads):
        sev = Severity(head.group(1))
        title = head.group(2).strip()
        start = head.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        # Stop at next major section if no more issues
        section = text[start:end]
        for stopper in (
            "\n## P1",
            "\n## P2",
            "\n## P3",
            "\n## Automated scanners",
            "\n## Plan to fix",
            "\n## Durability",
            "\n## Coverage",
            "\n## Theme",
            "\n## Disclaimer",
        ):
            idx = section.find(stopper)
            if idx != -1:
                section = section[:idx]
                break
        fields = _field_map(section)
        priority = fields.get("priority", "P3")
        if priority not in {"P1", "P2", "P3"}:
            priority = "P3"
        file_raw = fields.get("file", "unknown").strip("`")
        try:
            line = int(fields.get("line", "1") or "1")
        except ValueError:
            line = 1
        if line < 1:
            line = 1
        impact = fields.get("impact", "")
        if impact in {"_n/a_", "n/a"}:
            impact = ""
        code = fields.get("code example", "")
        if code.startswith("_MISSING"):
            code = "# example missing from imported report\npass"
        timing = fields.get("fix timing", "before launch")
        if timing not in {
            "immediately",
            "before launch",
            "after launch",
            "if time permits",
        }:
            timing = "before launch"
        # Schema requires impact+code for Critical/High
        if sev in {Severity.CRITICAL, Severity.HIGH}:
            if not impact.strip():
                impact = "See explanation (imported from prior markdown report)."
            if not code.strip():
                code = "# example missing from imported report\npass"
        try:
            issues.append(
                Issue(
                    severity=sev,
                    priority=priority,  # type: ignore[arg-type]
                    category=fields.get("category", "imported") or "imported",
                    file=file_raw or "unknown",
                    line=line,
                    title=title,
                    explanation=fields.get("explanation", "") or title,
                    impact=impact,
                    recommendedFix=fields.get("recommended fix", "") or "See prior report",
                    codeExample=code,
                    fixTiming=timing,  # type: ignore[arg-type]
                    owasp=fields.get("owasp") or None,
                    cwe=fields.get("cwe") or None,
                )
            )
        except Exception:  # noqa: BLE001 — skip malformed issue blocks
            continue

    if not issues:
        return None

    # Prefer parsed issues over header counts when they disagree
    report = FindingReport(
        confidence=confidence,
        summary=Summary(),
        issues=issues,
        llmCompleted=True,
        llmSkipped=False,
        durabilityGaps=[
            "Imported from prior markdown gate report (bootstrap until next fresh LLM)."
        ],
    )
    report.summary = report.recount_summary()
    counts = _COUNTS_RE.search(text)
    if counts:
        # Keep recount; header is informational only
        _ = counts
    return report


def bootstrap_markdown_from_out_dir(
    out_dir: Path | None,
) -> tuple[FindingReport, str, str, Path] | None:
    """Pick the markdown report with the most findings (not newest empty skip)."""
    if out_dir is None or not out_dir.is_dir():
        return None
    best: tuple[int, float, FindingReport, Path] | None = None
    for path in out_dir.glob("gate_review_report_*.md"):
        if path.name.endswith(".bak") or ".bak-" in path.name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        parsed = parse_markdown_report(text)
        if parsed is None or not parsed.issues:
            continue
        n = len(parsed.issues)
        mtime = path.stat().st_mtime
        if best is None or n > best[0] or (n == best[0] and mtime > best[1]):
            best = (n, mtime, parsed, path)
    if best is None:
        return None
    _, mtime, report, path = best
    from datetime import datetime, timezone

    saved_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    return report, saved_at, "", path
