from __future__ import annotations

import shlex
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from repolens_guided import (  # noqa: E402
    GuidedChoices,
    _has_cli_flag,
    _prompt_text,
    build_argv,
    default_local_path,
    format_command,
    full_pack_large_model_warning,
    is_large_local_model,
    list_installed_models,
    parse_ollama_list,
    parse_ollama_tags_json,
    probe_review_cli_caps,
    run_capture,
    suggest_timeout_seconds,
    validate_remote_value,
)


def test_suggest_timeout_by_model_size() -> None:
    assert suggest_timeout_seconds("qwen2.5:7b") == 900.0
    assert suggest_timeout_seconds("qwen2.5:14b") == 1800.0
    assert suggest_timeout_seconds("qwen2.5-coder:32b") == 3600.0
    assert suggest_timeout_seconds(None) == 900.0
    assert is_large_local_model("qwen2.5-coder:32b")
    assert not is_large_local_model("qwen2.5:7b")


def test_full_pack_large_model_warning() -> None:
    msg = full_pack_large_model_warning(
        model="qwen2.5-coder:32b",
        force_full=False,
        force_changed=False,
    )
    assert msg is not None
    assert "32b" in msg.lower() or "qwen2.5-coder:32b" in msg
    assert "3600" in msg
    assert (
        full_pack_large_model_warning(
            model="qwen2.5-coder:32b",
            force_full=False,
            force_changed=True,
        )
        is None
    )
    assert (
        full_pack_large_model_warning(
            model="qwen2.5:7b",
            force_full=True,
            force_changed=False,
        )
        is None
    )


def test_default_local_path_prefers_target() -> None:
    assert default_local_path({"TARGET": "/tmp/demo"}) == "/tmp/demo"
    assert default_local_path({"REPOLENS_PATH": "~/proj"}) == str(
        Path("~/proj").expanduser()
    )
    assert default_local_path({"TARGET": "  ", "REPOLENS_PATH": ""}) == "."
    assert default_local_path({}) == "."


def test_format_command_quotes_spaces() -> None:
    argv = ["repolens", "review", "--path", "/tmp/Demo Project"]
    formatted = format_command(argv)
    assert "Demo Project" in formatted
    assert shlex.split(formatted) == argv


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


def test_parse_ollama_tags_json_rejects_non_dict() -> None:
    assert parse_ollama_tags_json([]) == []
    assert parse_ollama_tags_json("models") == []
    assert parse_ollama_tags_json(None) == []
    assert parse_ollama_tags_json(42) == []


def test_build_argv_local_review_adaptive() -> None:
    choices = GuidedChoices(
        command="review",
        path="/tmp/demo",
        out="/tmp/demo/reports",
        scanners_only=False,
        dry_run=False,
        force_full=False,
        force_changed=False,
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
        force_changed=False,
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


def test_build_argv_dry_run_drops_model_timeout_full() -> None:
    choices = GuidedChoices(
        command="review",
        path="/tmp/demo",
        out="/tmp/demo/reports",
        scanners_only=False,
        dry_run=True,
        force_full=True,
        force_changed=False,
        full_audit=True,
        model="qwen2.5:7b",
        verbose=True,
        timeout=900.0,
        fmt="md",
        scanners="auto",
        fail_on=None,
        remote=None,
        ref=None,
    )
    argv = build_argv(choices)
    assert "--dry-run" in argv
    assert "--model" not in argv
    assert "--timeout" not in argv
    assert "--full" not in argv
    assert "--full-audit" not in argv


def test_build_argv_github_remote() -> None:
    choices = GuidedChoices(
        command="review",
        path=None,
        out="/tmp/out",
        scanners_only=False,
        dry_run=False,
        force_full=True,
        force_changed=False,
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


def test_build_argv_hf_remote() -> None:
    choices = GuidedChoices(
        command="architecture",
        path=None,
        out="./reports",
        scanners_only=False,
        dry_run=False,
        force_full=False,
        force_changed=False,
        full_audit=False,
        model=None,
        verbose=False,
        timeout=None,
        fmt="md",
        scanners="auto",
        fail_on=None,
        remote=("hf", "org/model"),
        ref="v1",
    )
    argv = build_argv(choices)
    assert argv[1] == "architecture"
    assert "--hf" in argv and "org/model" in argv
    assert "--ref" in argv and "v1" in argv
    assert "--path" not in argv


def test_build_argv_expands_user_path() -> None:
    choices = GuidedChoices(
        command="review",
        path="~/Demo Project",
        out="~/Demo Project/reports",
        scanners_only=False,
        dry_run=False,
        force_full=False,
        force_changed=False,
        full_audit=False,
        model=None,
        verbose=False,
        timeout=None,
        fmt="md",
        scanners="auto",
        fail_on=None,
        remote=None,
        ref=None,
    )
    argv = build_argv(choices)
    path = argv[argv.index("--path") + 1]
    out = argv[argv.index("--out") + 1]
    assert not path.startswith("~")
    assert not out.startswith("~")
    assert path.endswith("Demo Project")
    assert out.endswith(str(Path("Demo Project") / "reports"))


def test_has_cli_flag_full_not_full_audit() -> None:
    assert _has_cli_flag("  --full-audit  deeper architecture", "--full") is False
    assert _has_cli_flag("  --full  force full LLM pack", "--full") is True


def test_has_cli_flag_deep_not_confused_with_no_deep() -> None:
    assert _has_cli_flag("  --no-deep  single-shot", "--deep") is False
    assert _has_cli_flag("  --deep/--no-deep  multi-pass", "--deep") is True
    assert _has_cli_flag("  --deep/--no-deep  multi-pass", "--no-deep") is True


def test_probe_review_cli_caps_full_audit_does_not_enable_full() -> None:
    with patch("guided.caps.subprocess.run") as run:
        run.return_value = MagicMock(
            returncode=0,
            stdout="Usage\n  --full-audit\n  --verbose\n",
            stderr="",
        )
        caps = probe_review_cli_caps()
    assert caps.supports_full is False
    assert caps.supports_changed is False
    assert caps.supports_verbose is True
    assert caps.supports_deep is False


def test_probe_review_cli_caps_parses_help() -> None:
    with patch("guided.caps.subprocess.run") as run:
        run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "Usage\n  --verbose\n  --timeout FLOAT\n  --changed\n"
                "  --deep/--no-deep\n"
            ),
            stderr="",
        )
        caps = probe_review_cli_caps()
    assert caps.supports_verbose is True
    assert caps.supports_timeout is True
    assert caps.supports_full is False
    assert caps.supports_changed is True
    assert caps.supports_deep is True


def test_probe_review_cli_caps_empty_on_error() -> None:
    with patch(
        "guided.caps.subprocess.run",
        side_effect=OSError("missing"),
    ):
        caps = probe_review_cli_caps()
    assert caps.supports_verbose is False
    assert caps.supports_timeout is False
    assert caps.supports_full is False
    assert caps.supports_changed is False
    assert caps.supports_deep is False


def test_probe_review_cli_caps_empty_on_unexpected_error() -> None:
    with patch(
        "guided.caps.subprocess.run",
        side_effect=RuntimeError("boom"),
    ):
        caps = probe_review_cli_caps()
    assert caps.supports_verbose is False


def test_run_capture_returns_empty_on_failure() -> None:
    with patch(
        "guided.caps.subprocess.run",
        side_effect=TimeoutError("slow"),
    ):
        assert run_capture(["repolens", "review", "--help"], timeout=1) == ""


def test_validate_remote_value() -> None:
    assert validate_remote_value("github", "owner/repo") is None
    assert validate_remote_value("github", "bad") is not None
    assert validate_remote_value("github", "") is not None
    assert validate_remote_value("hf", "datasets/org/name") is None
    assert validate_remote_value("git-url", "https://github.com/o/r.git") is None
    assert validate_remote_value("git-url", "not-a-url") is not None


def test_prompt_text_uses_default_and_rejects_empty() -> None:
    with patch("builtins.input", side_effect=["", "  ", "ok"]):
        assert _prompt_text("Path") == "ok"
    with patch("builtins.input", side_effect=[""]):
        assert _prompt_text("Path", ".") == "."


def test_build_argv_changed_only() -> None:
    choices = GuidedChoices(
        command="review",
        path=".",
        out="./reports",
        scanners_only=False,
        dry_run=False,
        force_full=False,
        force_changed=True,
        full_audit=False,
        model=None,
        verbose=False,
        timeout=None,
        fmt="md",
        scanners="auto",
        fail_on=None,
        remote=None,
        ref=None,
    )
    argv = build_argv(choices)
    assert "--changed" in argv
    assert "--full" not in argv


def test_build_argv_emits_deep() -> None:
    choices = GuidedChoices(
        command="review",
        path="/tmp/demo",
        out="/tmp/demo/reports",
        scanners_only=False,
        dry_run=False,
        force_full=False,
        force_changed=False,
        full_audit=True,
        model=None,
        verbose=False,
        timeout=None,
        fmt="md",
        scanners="auto",
        fail_on=None,
        remote=None,
        ref=None,
        deep=True,
    )
    argv = build_argv(choices)
    assert "--deep" in argv
    assert "--no-deep" not in argv
    assert "--full-audit" in argv


def test_build_argv_emits_no_deep() -> None:
    choices = GuidedChoices(
        command="review",
        path="/tmp/demo",
        out="/tmp/demo/reports",
        scanners_only=False,
        dry_run=False,
        force_full=False,
        force_changed=False,
        full_audit=False,
        model=None,
        verbose=False,
        timeout=None,
        fmt="md",
        scanners="auto",
        fail_on=None,
        remote=None,
        ref=None,
        deep=False,
    )
    argv = build_argv(choices)
    assert "--no-deep" in argv
    assert "--deep" not in argv


def test_build_argv_omits_deep_when_unset() -> None:
    choices = GuidedChoices(
        command="review",
        path="/tmp/demo",
        out="/tmp/demo/reports",
        scanners_only=False,
        dry_run=False,
        force_full=False,
        force_changed=False,
        full_audit=False,
        model=None,
        verbose=False,
        timeout=None,
        fmt="md",
        scanners="auto",
        fail_on=None,
        remote=None,
        ref=None,
        deep=None,
    )
    argv = build_argv(choices)
    assert "--deep" not in argv
    assert "--no-deep" not in argv


def test_build_argv_scanners_only_drops_deep() -> None:
    choices = GuidedChoices(
        command="review",
        path=".",
        out="./reports",
        scanners_only=True,
        dry_run=False,
        force_full=False,
        force_changed=False,
        full_audit=False,
        model=None,
        verbose=False,
        timeout=None,
        fmt="md",
        scanners="auto",
        fail_on=None,
        remote=None,
        ref=None,
        deep=True,
    )
    argv = build_argv(choices)
    assert "--deep" not in argv
    assert "--no-deep" not in argv


def test_list_installed_models_prefers_ollama_list() -> None:
    with patch("guided.caps.subprocess.run") as run:
        run.return_value = MagicMock(
            returncode=0,
            stdout="NAME\nqwen2.5:7b\n",
            stderr="",
        )
        with patch("guided.caps.urllib.request.urlopen") as urlopen:
            assert list_installed_models() == ["qwen2.5:7b"]
            urlopen.assert_not_called()


def test_list_installed_models_falls_back_to_tags_api() -> None:
    with patch("guided.caps.subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        with patch("guided.caps.urllib.request.urlopen") as urlopen:
            resp = MagicMock()
            resp.read.return_value = b'{"models":[{"name":"fallback:1b"}]}'
            resp.__enter__.return_value = resp
            resp.__exit__.return_value = None
            urlopen.return_value = resp
            assert list_installed_models() == ["fallback:1b"]
