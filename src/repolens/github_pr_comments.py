"""Optional GitHub PR review comments for Critical/High (#29).

Anti-spam defaults:
- Max 3 comments per run (highest severity first)
- Crit/High only
- Idempotent: find prior RepoLens marker and PATCH in place
- Opt-in only (CLI flag / Action input; default off)
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from repolens.pr_summary import _critical_high, _safe_annotation_file, _truncate_example
from repolens.schema import FindingReport, Issue

_MAX_COMMENTS = 3
_MARKER_RE = re.compile(
    r"<!--\s*repolens-finding:(?P<sid>[0-9a-fA-F-]{36})\s*-->"
)
_API = "https://api.github.com"


@dataclass(frozen=True)
class PrCommentResult:
    created: int
    updated: int
    skipped: int
    errors: list[str]


def finding_marker(stable_id: str) -> str:
    return f"<!-- repolens-finding:{stable_id} -->"


def build_comment_body(issue: Issue) -> str:
    sid = (issue.stableId or "").strip() or "unknown"
    lines = [
        finding_marker(sid),
        "",
        f"**[{issue.severity.value}] {issue.title}**",
        "",
        f"- **Where:** `{issue.file}:{issue.line}`",
        f"- **Category:** `{issue.category}`",
        f"- **Fingerprint:** `{sid}`",
        f"- **Fix:** {issue.recommendedFix}",
    ]
    example = (issue.codeExample or "").strip()
    if example:
        lines.extend(["", "```", _truncate_example(example), "```"])
    lines.extend(
        [
            "",
            "_Posted by RepoLens (opt-in). Re-runs edit this comment in place "
            f"(max {_MAX_COMMENTS} Critical/High per run)._",
        ]
    )
    return "\n".join(lines)


def resolve_github_token() -> str | None:
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        val = os.environ.get(name, "").strip()
        if val:
            return val
    return None


def resolve_repo_slug() -> tuple[str, str] | None:
    raw = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if "/" not in raw:
        return None
    owner, repo = raw.split("/", 1)
    if owner and repo:
        return owner, repo
    return None


def resolve_pr_number(*, explicit: int | None = None) -> int | None:
    if explicit is not None and explicit > 0:
        return explicit
    event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    if not event_path:
        return None
    path = Path(event_path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    pr = data.get("pull_request") or {}
    num = pr.get("number") or data.get("number")
    try:
        n = int(num)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def select_issues_for_comments(
    report: FindingReport, *, max_comments: int = _MAX_COMMENTS
) -> list[Issue]:
    """Critical/High with stableId + safe path + line; capped."""
    out: list[Issue] = []
    for issue in _critical_high(report):
        if not (issue.stableId or "").strip():
            continue
        if _safe_annotation_file(issue.file) is None:
            continue
        if issue.line is None or issue.line < 1:
            continue
        out.append(issue)
        if len(out) >= max_comments:
            break
    return out


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "repolens-audit",
    }


def _list_review_comments(
    client: httpx.Client,
    *,
    owner: str,
    repo: str,
    pr: int,
) -> list[dict[str, Any]]:
    url = f"{_API}/repos/{owner}/{repo}/pulls/{pr}/comments"
    comments: list[dict[str, Any]] = []
    page = 1
    while page <= 5:
        response = client.get(url, params={"per_page": 100, "page": page})
        response.raise_for_status()
        batch = response.json()
        if not isinstance(batch, list) or not batch:
            break
        comments.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return comments


def _index_repolens_comments(
    comments: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in comments:
        body = str(row.get("body") or "")
        match = _MARKER_RE.search(body)
        if not match:
            continue
        indexed[match.group("sid").lower()] = row
    return indexed


def _pull_head_sha(
    client: httpx.Client, *, owner: str, repo: str, pr: int
) -> str:
    response = client.get(f"{_API}/repos/{owner}/{repo}/pulls/{pr}")
    response.raise_for_status()
    data = response.json()
    sha = ((data.get("head") or {}).get("sha")) or ""
    if not sha:
        raise RuntimeError("Pull request head SHA missing")
    return str(sha)


def post_or_update_review_comments(
    report: FindingReport,
    *,
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
    max_comments: int = _MAX_COMMENTS,
    client: httpx.Client | None = None,
) -> PrCommentResult:
    """Create or update up to *max_comments* inline review comments."""
    issues = select_issues_for_comments(report, max_comments=max_comments)
    if not issues:
        return PrCommentResult(0, 0, 0, [])

    owns = client is None
    client = client or httpx.Client(timeout=30.0, headers=_auth_headers(token))
    created = updated = skipped = 0
    errors: list[str] = []
    try:
        existing = _index_repolens_comments(
            _list_review_comments(client, owner=owner, repo=repo, pr=pr_number)
        )
        head_sha = _pull_head_sha(client, owner=owner, repo=repo, pr=pr_number)
        for issue in issues:
            sid = (issue.stableId or "").strip().lower()
            body = build_comment_body(issue)
            path = _safe_annotation_file(issue.file)
            assert path is not None  # filtered above
            prior = existing.get(sid)
            try:
                if prior and prior.get("id") is not None:
                    cid = int(prior["id"])
                    response = client.patch(
                        f"{_API}/repos/{owner}/{repo}/pulls/comments/{cid}",
                        json={"body": body},
                    )
                    if response.status_code >= 400:
                        errors.append(
                            f"update {sid}: HTTP {response.status_code} {response.text[:200]}"
                        )
                        skipped += 1
                    else:
                        updated += 1
                else:
                    payload = {
                        "body": body,
                        "commit_id": head_sha,
                        "path": path,
                        "line": int(issue.line),
                        "side": "RIGHT",
                    }
                    response = client.post(
                        f"{_API}/repos/{owner}/{repo}/pulls/{pr_number}/comments",
                        json=payload,
                    )
                    if response.status_code >= 400:
                        # Line may not be in the PR diff — skip quietly with note.
                        errors.append(
                            f"create {sid}@{path}:{issue.line}: "
                            f"HTTP {response.status_code} {response.text[:200]}"
                        )
                        skipped += 1
                    else:
                        created += 1
            except (httpx.HTTPError, TypeError, ValueError) as exc:
                errors.append(f"{sid}: {exc}")
                skipped += 1
    finally:
        if owns:
            client.close()
    return PrCommentResult(created, updated, skipped, errors)
