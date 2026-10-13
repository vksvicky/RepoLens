"""Comprehensive Right-BICEP and edge-case tests across CLI, pipeline, and heuristics.

Covers:
- Right: happy paths and core contracts
- Boundary: edge limits, empty sets, thresholds, IPv6, URL userinfo/query/fragment variations
- Inverse: idempotency of sanitization, done + remaining == total file count invariants
- Cross-check: which catalog commands vs resolved_argv expansion
- Error conditions: malformed URLs, corrupted JSONL journals, missing/invalid scenarios
- Performance/Properties: resilient parsing without catastrophic stalls
"""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repolens.cli import app
from repolens.cli.commands_which import _CATALOG, _SCENARIOS
from repolens.cli.presets import ReviewFlagBag, apply_preset
from repolens.cli.resolved_argv import (
    ResolvedInvocation,
    build_expanded_argv,
    command_for_provenance,
    sanitize_invoked_command,
    strip_url_userinfo,
)
from repolens.heuristics.ci_gaps import find_ci_gaps
from repolens.heuristics.scripts_hygiene import find_script_credential_hygiene, find_todo_density
from repolens.inventory import FileEntry
from repolens.pipeline.journal import journal_path
from repolens.pipeline.pass_progress import continue_line, file_work_line, saved_pass_rerun_line

runner = CliRunner()


# ---------------------------------------------------------------------------
# 1. Right-BICEP: repolens which & Cross-Check
# ---------------------------------------------------------------------------


def test_which_help_shows_all_available_scenarios() -> None:
    """Boundary / Error: invoking --help displays all scenarios clearly."""
    result = runner.invoke(app, ["which", "--help"])
    assert result.exit_code == 0
    for name in _SCENARIOS:
        assert name in result.stdout


def test_which_cross_check_semantic_expansion() -> None:
    """Cross-check: which command's semantic intent maps to expected resolved expansion."""
    # When repolens review --preset pr --path . is resolved by CLI:
    pr_bag = apply_preset("pr", ReviewFlagBag())
    pr_expanded = build_expanded_argv(
        ResolvedInvocation(
            mode="review",
            path=".",
            scanners_only=pr_bag.scanners_only,
            deep=pr_bag.deep,
        )
    )
    # The operator command is what 'which' suggests:
    assert _CATALOG["pr"].command == "repolens review --preset pr --path ."
    # The reproducible expanded argv resolves the preset flags:
    assert shlex.join(pr_expanded) == "repolens review --path . --scanners-only --no-deep"

    # changed:
    changed_bag = apply_preset("changed", ReviewFlagBag())
    changed_expanded = build_expanded_argv(
        ResolvedInvocation(
            mode="review",
            path=".",
            git_diff=changed_bag.git_diff,
            deep=changed_bag.deep,
            timeout=changed_bag.timeout,
        )
    )
    assert _CATALOG["changed"].command == "repolens review --preset changed --path ."
    assert shlex.join(changed_expanded) == (
        "repolens review --path . --git-diff auto --deep --timeout 900"
    )

    # release:
    rel_bag = apply_preset("release", ReviewFlagBag())
    rel_expanded = build_expanded_argv(
        ResolvedInvocation(
            mode="review",
            path=".",
            force_full=rel_bag.force_full,
            full_audit=rel_bag.full_audit,
            deep=rel_bag.deep,
            timeout=rel_bag.timeout,
        )
    )
    assert _CATALOG["release"].command == "repolens review --preset release --path ."
    assert shlex.join(rel_expanded) == (
        "repolens review --path . --full --full-audit --deep --timeout 3600"
    )

    # audit / m-and-a:
    audit_expanded = build_expanded_argv(
        ResolvedInvocation(
            mode="review",
            path=".",
            force_full=True,
            full_audit=True,
            deep=True,
            timeout=3600.0,
            ratchet=True,
            verify_findings=True,
        )
    )
    assert _CATALOG["audit"].command == "repolens audit --path ."
    assert _CATALOG["m-and-a"].command == "repolens audit --path ."
    assert "--ratchet" in audit_expanded
    assert "--verify-findings" in audit_expanded

    # security:
    sec_expanded = build_expanded_argv(ResolvedInvocation(mode="sentinel", path="."))
    assert _CATALOG["security"].command == shlex.join(sec_expanded)

    # architecture:
    arch_expanded = build_expanded_argv(ResolvedInvocation(mode="architecture", path="."))
    assert _CATALOG["architecture"].command == shlex.join(arch_expanded)


@pytest.mark.parametrize("scenario", _SCENARIOS)
def test_which_case_insensitivity_and_whitespace(scenario: str) -> None:
    """Boundary: uppercase and surrounding whitespace are normalized."""
    result = runner.invoke(app, ["which", f"  {scenario.upper()}  "])
    assert result.exit_code == 0
    assert result.stdout.strip() == _CATALOG[scenario].command


def test_which_json_output_is_pure_json() -> None:
    """Boundary / Stub check: --json prints only valid JSON on stdout."""
    result = runner.invoke(app, ["which", "release", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["scenario"] == "release"
    assert "repolens review --preset release" in data["command"]
    assert "3600" in data["why"]


# ---------------------------------------------------------------------------
# 2. Right-BICEP: resolved_argv & strip_url_userinfo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        # Standard user:pass
        ("http://user:pass@example.com/repo.git", "http://example.com/repo.git"),
        ("https://user:pass@example.com/repo.git", "https://example.com/repo.git"),
        # User only
        ("https://user@example.com/repo.git", "https://example.com/repo.git"),
        # Password only
        ("https://:secret@example.com/repo.git", "https://example.com/repo.git"),
        # Non-standard port with credentials
        ("https://user:token@github.com:8443/org/repo.git", "https://github.com:8443/org/repo.git"),
        # IPv6 literal host with credentials and port
        ("http://admin:secret@[::1]:8080/repo.git", "http://[::1]:8080/repo.git"),
        # Query params and fragments stripped even without credentials
        ("https://github.com/org/repo.git?token=123#branch", "https://github.com/org/repo.git"),
        ("https://user:pass@github.com/org/repo.git?access_token=xyz#top", "https://github.com/org/repo.git"),
        # HuggingFace token in URL
        ("https://hf_token_abc@huggingface.co/models/custom", "https://huggingface.co/models/custom"),
        # Passthrough protocols
        ("ssh://git@github.com:org/repo.git", "ssh://git@github.com:org/repo.git"),
        ("git@github.com:org/repo.git", "git@github.com:org/repo.git"),
        ("file:///local/path/to/repo", "file:///local/path/to/repo"),
        ("", ""),
        ("just-a-plain-string", "just-a-plain-string"),
    ],
)
def test_strip_url_userinfo_boundaries(raw_url: str, expected: str) -> None:
    """Boundary: diverse URL formats, IPv6, ports, tokens, and non-http schemes."""
    assert strip_url_userinfo(raw_url) == expected


def test_sanitize_invoked_command_idempotency() -> None:
    """Inverse: sanitizing an already sanitized command leaves it identical."""
    original = [
        "repolens",
        "review",
        "--git-url",
        "https://token:secret@host.com/repo.git",
        "--path",
        ".",
    ]
    sanitized = sanitize_invoked_command(original)
    tokens = shlex.split(sanitized)
    assert sanitize_invoked_command(tokens) == sanitized


def test_command_for_provenance_mocking(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mocking / Error: provenance selects repolens sys.argv vs fallback."""
    fallback = ["repolens", "review", "--path", "."]

    # When running under pytest, sys.argv starts with pytest -> returns fallback
    monkeypatch.setattr(sys, "argv", ["pytest", "tests/test_something.py"])
    assert command_for_provenance(fallback) == "repolens review --path ."

    # When sys.argv is a direct repolens binary
    monkeypatch.setattr(sys, "argv", ["/opt/homebrew/bin/repolens", "audit", "--path", "."])
    assert command_for_provenance(fallback) == "repolens audit --path ."

    # When sys.argv is python -m repolens
    py_argv = ["/usr/bin/python3", "-m", "repolens", "sentinel", "--path", "src"]
    monkeypatch.setattr(sys, "argv", py_argv)
    assert command_for_provenance(fallback) == "repolens sentinel --path src"


def test_resolved_argv_empty_and_optional_fields() -> None:
    """Boundary: empty collections and None fields omit spurious flags."""
    argv = build_expanded_argv(
        ResolvedInvocation(
            mode="review",
            path=None,
            git_url=None,
            import_sarif=(),
            retry_passes=(),
            packs=(),
            deep=None,
            verify_findings=None,
            role_packs=None,
            fallback=None,
            model_lock=None,
        )
    )
    assert argv == ["repolens", "review"]


# ---------------------------------------------------------------------------
# 3. Right-BICEP: pass_progress.py & Journal Invariants
# ---------------------------------------------------------------------------


def test_file_work_line_invariants_and_clamping() -> None:
    """Right / Boundary / Inverse: progress line calculation and clamping."""
    # Clamping done > total
    line_over = file_work_line(50, 40)
    assert "50 of 40 file checks done (100%). 0 files still to go." == line_over

    # Clamping negative done
    line_neg = file_work_line(-10, 20)
    assert "0 of 20 file checks done (0%). 20 files still to go." == line_neg

    # Large values
    line_large = file_work_line(100_000, 200_000)
    assert "100000 of 200000 file checks done (50%). 100000 files still to go." == line_large


def test_saved_pass_rerun_line_singular_plural() -> None:
    """Right / Boundary: singular '1 file' vs plural 'N files'."""
    assert "1 file" in saved_pass_rerun_line("P1", 1, 2)
    assert "2 files" in saved_pass_rerun_line("P1", 1, 2)
    assert "5 files" in saved_pass_rerun_line("P1", 5, 10)


def test_continue_line_corrupted_journal_resilience(tmp_path: Path) -> None:
    """Error / Resilience: journal with malformed JSON, empty lines, and non-dict objects."""
    jp = journal_path(tmp_path)
    jp.parent.mkdir(parents=True, exist_ok=True)
    # Write garbage JSON lines
    jp.write_text(
        "\n"
        "NOT JSON AT ALL\n"
        '{"ts": "2026-10-12T00:00:00Z"}\n'  # Missing 'event' key
        '[1, 2, 3]\n'  # List instead of dict
        '{"event": "interrupted", "finished": ["P1 Security"]}\n'
        "CORRUPT TRAILING LINE\n",
        encoding="utf-8",
    )
    # Should not raise exception
    res = continue_line(tmp_path)
    assert res is None or "P1 Security" in res


# ---------------------------------------------------------------------------
# 4. Right-BICEP: Fast-Brain Heuristics Boundaries
# ---------------------------------------------------------------------------


def test_todo_density_exact_threshold_boundary(tmp_path: Path) -> None:
    """Boundary: exactly 7 markers (below default min 8) vs exactly 8 markers (triggers)."""
    below = tmp_path / "below.py"
    below.write_text("\n".join(f"# TODO: item {i}" for i in range(7)) + "\n", encoding="utf-8")

    at_threshold = tmp_path / "at_threshold.py"
    body = "\n".join(f"# TODO: item {i}" for i in range(8)) + "\n"
    at_threshold.write_text(body, encoding="utf-8")

    entries = [
        FileEntry(path=below, relative="below.py", size=below.stat().st_size, priority_band=3),
        FileEntry(
            path=at_threshold,
            relative="at_threshold.py",
            size=at_threshold.stat().st_size,
            priority_band=3,
        ),
    ]

    issues = find_todo_density(entries, min_markers=8)
    files_flagged = [i.file for i in issues]
    assert "below.py" not in files_flagged
    assert "at_threshold.py" in files_flagged


@pytest.mark.parametrize("ext", [".sh", ".bash", ".zsh", ".ps1"])
def test_script_credential_hygiene_all_script_extensions(tmp_path: Path, ext: str) -> None:
    """Right / Boundary: all script suffixes are checked."""
    script = tmp_path / f"deploy{ext}"
    script.write_text("export PASSWORD='raw_secret'\n", encoding="utf-8")
    entry = FileEntry(
        path=script, relative=f"deploy{ext}", size=script.stat().st_size, priority_band=3
    )

    issues = find_script_credential_hygiene([entry])
    assert len(issues) == 1
    assert issues[0].category == "heuristic.scripts_hygiene"


@pytest.mark.parametrize(
    "secret_manager", ["keychain", "1password", "op read", "vault", "secret_manager"]
)
def test_script_credential_hygiene_secret_manager_exemption(
    tmp_path: Path, secret_manager: str
) -> None:
    """Right / Inverse: mentioning keychain or secret manager suppresses the finding."""
    script = tmp_path / "safe_deploy.sh"
    script.write_text(
        f"export APP_PASSWORD=$(get_credential)\n# Uses {secret_manager} to resolve credentials\n",
        encoding="utf-8",
    )
    entry = FileEntry(
        path=script, relative="safe_deploy.sh", size=script.stat().st_size, priority_band=3
    )

    issues = find_script_credential_hygiene([entry])
    assert issues == []


def test_ci_gaps_multiple_manifests_and_codeql_action_hint(tmp_path: Path) -> None:
    """Right / Boundary: monorepo with multiple manifests and CodeQL action in workflows."""
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "Cargo.toml").write_text("[package]", encoding="utf-8")

    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    # Workflow uses github/codeql-action
    codeql_wf = (
        "name: Security\njobs:\n  analyze:\n    steps:\n      "
        "- uses: github/codeql-action/init@v3\n"
    )
    (wf_dir / "security.yaml").write_text(codeql_wf, encoding="utf-8")
    # Missing Dependabot only
    entries = [
        FileEntry(path=tmp_path / "package.json", relative="package.json", size=2, priority_band=3),
        FileEntry(path=tmp_path / "Cargo.toml", relative="Cargo.toml", size=9, priority_band=3),
    ]

    issues = find_ci_gaps(tmp_path, entries)
    assert len(issues) == 1
    issue = issues[0]
    # CodeQL was detected via action reference, so only Dependabot is missing
    assert "Dependabot" in issue.title
    assert "CodeQL" not in issue.title
