"""Exact token lists for the resolved-argv builder."""

from __future__ import annotations

from repolens.cli.resolved_argv import (
    ResolvedInvocation,
    build_expanded_argv,
    sanitize_invoked_command,
)


def test_preset_pr_token_list() -> None:
    argv = build_expanded_argv(
        ResolvedInvocation(
            mode="review",
            path=".",
            scanners_only=True,
            deep=False,
            scanners="auto",
            fmt="md",
        )
    )
    assert argv == ["repolens", "review", "--path", ".", "--scanners-only", "--no-deep"]


def test_audit_expands_as_review_with_ratchet_and_verify() -> None:
    argv = build_expanded_argv(
        ResolvedInvocation(
            mode="review",
            path=".",
            force_full=True,
            full_audit=True,
            deep=True,
            timeout=3600.0,
            ratchet=True,
            verify_findings=True,
            scanners="auto",
            fmt="md",
        )
    )
    assert argv == [
        "repolens",
        "review",
        "--path",
        ".",
        "--full",
        "--full-audit",
        "--deep",
        "--timeout",
        "3600",
        "--ratchet",
        "--verify-findings",
    ]


def test_explicit_no_deep_overrides_release_shape() -> None:
    argv = build_expanded_argv(
        ResolvedInvocation(
            mode="review",
            path=".",
            force_full=True,
            full_audit=True,
            deep=False,
            timeout=3600,
            ratchet=True,
            verify_findings=True,
        )
    )
    assert "--no-deep" in argv
    assert "--deep" not in argv


def test_deep_none_omits_deep_flags() -> None:
    argv = build_expanded_argv(ResolvedInvocation(mode="review", path=".", deep=None))
    assert "--deep" not in argv
    assert "--no-deep" not in argv


def test_verify_false_emits_no_verify_findings() -> None:
    argv = build_expanded_argv(
        ResolvedInvocation(mode="review", path=".", verify_findings=False)
    )
    assert "--no-verify-findings" in argv
    assert "--verify-findings" not in argv


def test_omits_scanner_and_format_defaults() -> None:
    argv = build_expanded_argv(
        ResolvedInvocation(mode="review", path=".", scanners="auto", fmt="md")
    )
    assert "--scanners" not in argv
    assert "--format" not in argv


def test_emits_behavior_flags_when_set() -> None:
    argv = build_expanded_argv(
        ResolvedInvocation(
            mode="sentinel",
            path="src",
            ci=True,
            model="qwen",
            deep_passes=1,
            sarif=True,
            role_packs=False,
            import_sarif=("a.sarif", "b.sarif"),
            require_scanners=True,
            since="main",
            retry_passes=("p1",),
            packs=("fintech",),
            trust_project=True,
            dry_run=True,
            scanners="gitleaks,semgrep",
            fmt="both",
            fail_on="HIGH",
            review_mode="diff",
        )
    )
    assert argv[:4] == ["repolens", "sentinel", "--path", "src"]
    for token in (
        "--dry-run",
        "--ci",
        "--model",
        "qwen",
        "--deep-passes",
        "1",
        "--sarif",
        "--no-role-packs",
        "--import-sarif",
        "a.sarif",
        "b.sarif",
        "--require-scanners",
        "--since",
        "main",
        "--retry-pass",
        "p1",
        "--pack",
        "fintech",
        "--trust-project-config",
        "--scanners",
        "gitleaks,semgrep",
        "--format",
        "both",
        "--fail-on",
        "HIGH",
        "--mode",
        "diff",
    ):
        assert token in argv


def test_git_url_userinfo_stripped() -> None:
    argv = build_expanded_argv(
        ResolvedInvocation(
            mode="review",
            git_url="https://user:token@github.com/org/repo.git",
        )
    )
    assert "https://github.com/org/repo.git" in argv
    assert "token" not in argv
    assert "user:token" not in " ".join(argv)


def test_sanitize_invoked_command_normalizes_argv0_and_urls() -> None:
    command = sanitize_invoked_command(
        [
            "/usr/local/bin/repolens",
            "review",
            "--git-url",
            "https://token:secret@github.com/org/repo.git",
            "--path",
            ".",
        ]
    )
    assert command.startswith("repolens review ")
    assert "secret" not in command
    assert "https://github.com/org/repo.git" in command


def test_sanitize_python_module_invocation() -> None:
    command = sanitize_invoked_command(
        ["/usr/bin/python", "-m", "repolens", "which", "pr"]
    )
    assert command == "repolens which pr"
