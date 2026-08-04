"""Source resolver — URL parse, auth, clone argv (no network)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repolens.sources import (
    SourceError,
    build_github_url,
    cleanup_source,
    parse_github_slug,
    resolve_github_token,
    resolve_source,
    select_source,
)


def test_parse_github_slug_ok() -> None:
    assert parse_github_slug("owner/repo") == ("owner", "repo")
    assert parse_github_slug("owner/repo.git") == ("owner", "repo")


def test_parse_github_slug_rejects_bad() -> None:
    with pytest.raises(SourceError):
        parse_github_slug("not-a-slug")
    with pytest.raises(SourceError):
        parse_github_slug("a/b/c")


def test_build_github_url() -> None:
    assert build_github_url("acme", "widgets") == "https://github.com/acme/widgets.git"


def test_select_source_default_path() -> None:
    kind, value = select_source(path=None, git_url=None, github=None)
    assert kind == "path"
    assert value == Path(".")


def test_select_source_mutual_exclusion() -> None:
    with pytest.raises(SourceError, match="exactly one"):
        select_source(path=Path("/tmp/x"), git_url="https://example.com/a.git", github=None)
    with pytest.raises(SourceError, match="exactly one"):
        select_source(path=Path("."), git_url=None, github="o/r")


def test_select_source_github_with_default_none_path() -> None:
    kind, value = select_source(path=None, git_url=None, github="owner/repo")
    assert kind == "github"
    assert value == "owner/repo"


def test_resolve_github_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert resolve_github_token() == "ghp_test"


def test_resolve_github_token_gh_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    def fake_run(args, **kwargs):  # noqa: ANN001
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = "cli_token\n"
        completed.stderr = ""
        return completed

    with patch("repolens.sources.subprocess.run", side_effect=fake_run):
        assert resolve_github_token() == "cli_token"


def test_resolve_local_path(tmp_path: Path) -> None:
    resolved = resolve_source(kind="path", value=str(tmp_path), ref=None)
    assert resolved.root == tmp_path.resolve()
    assert resolved.ephemeral is False
    cleanup_source(resolved)
    assert tmp_path.exists()


def test_resolve_git_url_clones_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):  # noqa: ANN001
        calls.append(list(args))
        # Simulate git clone creating the destination directory
        if "clone" in args:
            dest = Path(args[-1])
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "README.md").write_text("ok\n", encoding="utf-8")
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = ""
        completed.stderr = ""
        return completed

    with (
        patch("repolens.sources.subprocess.run", side_effect=fake_run),
        patch("repolens.sources.tempfile.mkdtemp", return_value=str(tmp_path / "work")),
    ):
        (tmp_path / "work").mkdir()
        resolved = resolve_source(
            kind="git-url",
            value="https://github.com/acme/widgets.git",
            ref="main",
        )
        assert resolved.ephemeral is True
        assert (resolved.root / "README.md").is_file()
        # Token must not appear in any argv
        flat = " ".join(" ".join(c) for c in calls)
        assert "ghp_" not in flat
        assert "clone" in flat
        parent = resolved.root.parent
        cleanup_source(resolved)
        assert not resolved.root.exists()
        assert not parent.exists()


def test_clone_failure_raises_source_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    def fake_run(args, **kwargs):  # noqa: ANN001
        completed = MagicMock()
        completed.returncode = 128
        completed.stdout = ""
        completed.stderr = "fatal: repository not found"
        return completed

    with (
        patch("repolens.sources.subprocess.run", side_effect=fake_run),
        patch("repolens.sources.tempfile.mkdtemp", return_value=str(tmp_path / "work2")),
    ):
        (tmp_path / "work2").mkdir()
        with pytest.raises(SourceError, match="Clone failed"):
            resolve_source(kind="github", value="missing/repo", ref=None)
