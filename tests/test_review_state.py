"""CodeQL action pins and explicit review-phase state."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SHA = re.compile(r"[0-9a-f]{40}")


def test_codeql_actions_are_pinned_to_commits() -> None:
    text = (ROOT / ".github" / "workflows" / "codeql.yml").read_text(encoding="utf-8")
    uses = re.findall(r"uses:\s*(\S+)", text)
    codeql = [item for item in uses if item.startswith("github/codeql-action/")]
    assert len(codeql) == 3
    for item in codeql:
        _repo, _sep, rev = item.partition("@")
        assert _SHA.fullmatch(rev), item
        assert rev != "v3"


def test_run_review_phases_take_explicit_state() -> None:
    source = (ROOT / "src" / "repolens" / "pipeline" / "run.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    review = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_review"
    )
    assert not any(isinstance(node, ast.Nonlocal) for node in ast.walk(review))
    assert not any(isinstance(node, ast.FunctionDef) for node in review.body)
    built = [
        node
        for node in ast.walk(review)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ReviewRun"
    ]
    assert built
