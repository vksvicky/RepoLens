from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from repolens_guided import (  # noqa: E402
    GuidedChoices,
    build_argv,
    format_command,
    parse_ollama_list,
    parse_ollama_tags_json,
)


def test_format_command_quotes_spaces() -> None:
    assert "Demo Project" in format_command(
        ["repolens", "review", "--path", "/tmp/Demo Project"]
    )


def test_parse_ollama_list_skips_header() -> None:
    text = """NAME           ID       SIZE
qwen2.5:7b     abc      4.7 GB
llama3.2:3b    def      2.0 GB
"""
    assert parse_ollama_list(text) == ["qwen2.5:7b", "llama3.2:3b"]


def test_parse_ollama_tags_json() -> None:
    payload = {
        "models": [
            {"name": "qwen2.5:7b"},
            {"model": "mistral:7b"},
            {"name": ""},
        ]
    }
    assert parse_ollama_tags_json(payload) == ["qwen2.5:7b", "mistral:7b"]


def test_build_argv_local_review_adaptive() -> None:
    choices = GuidedChoices(
        command="review",
        path="/tmp/demo",
        out="/tmp/demo/reports",
        scanners_only=False,
        dry_run=False,
        force_full=False,
        full_audit=False,
        model=None,
        verbose=True,
        timeout=900.0,
        fmt="md",
        scanners="auto",
        fail_on=None,
        remote=None,
        ref=None,
    )
    argv = build_argv(choices)
    assert argv[:3] == ["repolens", "review", "--path"]
    assert "--path" in argv and "/tmp/demo" in argv
    assert "--out" in argv and "/tmp/demo/reports" in argv
    assert "--verbose" in argv
    assert "--timeout" in argv and "900" in argv
    assert "--scanners-only" not in argv
    assert "--full" not in argv
    assert "--model" not in argv


def test_build_argv_scanners_only_sentinel() -> None:
    choices = GuidedChoices(
        command="sentinel",
        path=".",
        out="./reports",
        scanners_only=True,
        dry_run=False,
        force_full=False,
        full_audit=False,
        model="qwen2.5:7b",  # must be ignored when scanners_only
        verbose=False,
        timeout=None,
        fmt="md",
        scanners="auto",
        fail_on="HIGH",
        remote=None,
        ref=None,
    )
    argv = build_argv(choices)
    assert argv[1] == "sentinel"
    assert "--scanners-only" in argv
    assert "--model" not in argv
    assert "--fail-on" in argv and "HIGH" in argv


def test_build_argv_github_remote() -> None:
    choices = GuidedChoices(
        command="review",
        path=None,
        out="/tmp/out",
        scanners_only=False,
        dry_run=False,
        force_full=True,
        full_audit=True,
        model="llama3.2:3b",
        verbose=True,
        timeout=1800.0,
        fmt="both",
        scanners="off",
        fail_on=None,
        remote=("github", "owner/repo"),
        ref="main",
    )
    argv = build_argv(choices)
    assert "--github" in argv and "owner/repo" in argv
    assert "--ref" in argv and "main" in argv
    assert "--path" not in argv
    assert "--full" in argv
    assert "--full-audit" in argv
    assert "--model" in argv and "llama3.2:3b" in argv
    assert "--format" in argv and "both" in argv
    assert "--scanners" in argv and "off" in argv
