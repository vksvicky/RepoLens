"""CI argv assembly for GitHub Action / scripts."""

from __future__ import annotations

import pytest

from repolens.ci_args import build_review_argv, has_llm_api_key


def test_has_llm_api_key_detects_known_envs() -> None:
    assert has_llm_api_key({"OPENAI_API_KEY": "sk-test"}) is True
    assert has_llm_api_key({"ANTHROPIC_API_KEY": "x"}) is True
    assert has_llm_api_key({"DEEPSEEK_API_KEY": "x"}) is True
    assert has_llm_api_key({"REPOLENS_API_KEY": "x"}) is True
    assert has_llm_api_key({"PATH": "/usr/bin"}) is False
    assert has_llm_api_key({"OPENAI_API_KEY": ""}) is False


def test_build_dry_run() -> None:
    argv = build_review_argv(mode="sentinel", path="/tmp/p", run="dry-run", fail_on="")
    assert argv[:2] == ["repolens", "sentinel"]
    assert "--path" in argv and "/tmp/p" in argv
    assert "--dry-run" in argv
    assert "--scanners-only" not in argv


def test_build_scanners_only() -> None:
    argv = build_review_argv(run="scanners-only", fail_on="HIGH")
    assert "--scanners-only" in argv
    assert "--fail-on" in argv and "HIGH" in argv


def test_build_auto_without_key_uses_scanners_only() -> None:
    argv = build_review_argv(run="auto", has_key=False, fail_on="")
    assert "--scanners-only" in argv
    assert "--dry-run" not in argv


def test_build_auto_with_key_runs_full_review() -> None:
    argv = build_review_argv(run="auto", has_key=True, scanners="gitleaks", fail_on="CRITICAL")
    assert "--scanners-only" not in argv
    assert "--dry-run" not in argv
    assert "--scanners" in argv and "gitleaks" in argv
    assert "--fail-on" in argv and "CRITICAL" in argv


def test_build_llm_without_key_raises() -> None:
    with pytest.raises(ValueError, match="API key"):
        build_review_argv(run="llm", has_key=False)


def test_build_llm_with_key() -> None:
    argv = build_review_argv(run="llm", has_key=True, mode="architecture")
    assert argv[1] == "architecture"
    assert "--scanners-only" not in argv


def test_require_scanners_flag() -> None:
    argv = build_review_argv(run="scanners-only", require_scanners=True, fail_on="")
    assert "--require-scanners" in argv


def test_unknown_run_raises() -> None:
    with pytest.raises(ValueError, match="run"):
        build_review_argv(run="nope", has_key=True)
