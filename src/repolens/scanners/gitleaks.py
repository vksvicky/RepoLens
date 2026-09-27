"""gitleaks secrets adapter.

Working-tree scan uses ``--no-git``. A second pass, only inside a git
checkout, scans commit history and files those hits separately from the
``.gitignore`` heuristic.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from repolens.scanners.base import ScannerResult, resolve_binary
from repolens.schema import Issue, ScannerRun, Severity

_HISTORY_CATEGORY = "sec.repo_hygiene_secrets"


def run_gitleaks(root: Path) -> ScannerResult:
    binary = resolve_binary("gitleaks")
    if binary is None:
        return ScannerResult(
            run=ScannerRun(tool="gitleaks", status="skipped", detail="not found on PATH or cache")
        )
    tree = _detect(binary, root, history=False)
    if tree.run.status == "failed":
        return tree
    if not _is_git_checkout(root):
        return tree
    history = _detect(binary, root, history=True)
    if history.run.status == "failed":
        return ScannerResult(
            run=ScannerRun(
                tool="gitleaks",
                status="ran",
                findingCount=len(tree.issues),
                detail=f"git history scan failed — {history.run.detail}",
            ),
            issues=list(tree.issues),
        )
    issues = [*tree.issues, *history.issues]
    return ScannerResult(
        run=ScannerRun(tool="gitleaks", status="ran", findingCount=len(issues)),
        issues=issues,
    )


def _is_git_checkout(root: Path) -> bool:
    return (root / ".git").exists()


def _detect(binary: Path, root: Path, *, history: bool) -> ScannerResult:
    command = [
        str(binary),
        "detect",
        "--source",
        str(root),
        "-f",
        "json",
        "-r",
        "/dev/stdout",
    ]
    if history:
        # All branches. Omitting --no-git makes gitleaks walk git log.
        command.append("--log-opts=--all")
    else:
        command.append("--no-git")
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
    )
    # gitleaks exits 1 when secrets are found.
    if completed.returncode not in {0, 1}:
        return ScannerResult(
            run=ScannerRun(
                tool="gitleaks",
                status="failed",
                detail=(completed.stderr or completed.stdout or "gitleaks failed")[:300],
            )
        )
    raw = completed.stdout.strip()
    if not raw:
        return ScannerResult(run=ScannerRun(tool="gitleaks", status="ran", findingCount=0))
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ScannerResult(
            run=ScannerRun(tool="gitleaks", status="failed", detail="invalid JSON output")
        )
    if not isinstance(data, list):
        data = []
    issues = [_issue_from_item(item, history=history) for item in data if isinstance(item, dict)]
    return ScannerResult(
        run=ScannerRun(tool="gitleaks", status="ran", findingCount=len(issues)),
        issues=issues,
    )


def _issue_from_item(item: dict, *, history: bool) -> Issue:
    file_path = str(item.get("File") or item.get("file") or "unknown")
    line = int(item.get("StartLine") or item.get("line") or 1)
    rule = str(item.get("RuleID") or item.get("Description") or "secret")
    desc = str(item.get("Description") or rule)
    if history:
        commit = str(item.get("Commit") or "").strip()
        short = commit[:12]
        where = f" Commit {short}." if short else ""
        return Issue(
            severity=Severity.HIGH,
            priority="P1",
            category=_HISTORY_CATEGORY,
            file=file_path,
            line=max(line, 1),
            title=f"Git history secret: {rule}",
            explanation=(
                f"{desc} Present in git history (committed), separate from "
                f".gitignore hygiene.{where}"
            ),
            impact=(
                "A committed secret stays in clones and forks after the file is deleted. "
                "Anyone with repo access can recover it."
            ),
            recommendedFix=(
                "Rotate the credential. Deleting the file does not remove it from git "
                "history. Load the replacement from a secret manager or environment."
            ),
            codeExample='value = os.environ["SECRET_NAME"]  # do not commit the value',
            fixTiming="immediately",
        )
    return Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="gitleaks",
        file=file_path,
        line=max(line, 1),
        title=f"Secret detected: {rule}",
        explanation=desc,
        impact="Credential exposure can enable account takeover or data theft.",
        recommendedFix="Remove the secret, rotate it, and load from a secret manager / env.",
        codeExample='value = os.environ["SECRET_NAME"]  # do not hardcode',
        fixTiming="immediately",
    )
