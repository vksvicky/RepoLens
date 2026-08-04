"""Source resolver — URL parse, auth, clone argv (no network)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repolens.sources import (
    SourceError,
    build_bitbucket_url,
    build_github_url,
    build_hf_url,
    cleanup_source,
    parse_bitbucket_slug,
    parse_github_slug,
    parse_hf_id,
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


def test_parse_bitbucket_slug() -> None:
    assert parse_bitbucket_slug("ws/repo") == ("ws", "repo")


def test_parse_hf_id_model_dataset_space() -> None:
    assert parse_hf_id("org/model") == "org/model"
    assert parse_hf_id("datasets/org/data") == "datasets/org/data"
    assert parse_hf_id("spaces/org/app") == "spaces/org/app"


def test_parse_hf_id_rejects_bad() -> None:
    with pytest.raises(SourceError):
        parse_hf_id("noslash")
    with pytest.raises(SourceError):
        parse_hf_id("a/b/c/d")


def test_build_urls() -> None:
    assert build_github_url("acme", "widgets") == "https://github.com/acme/widgets.git"
    assert build_bitbucket_url("acme", "widgets") == "https://bitbucket.org/acme/widgets.git"
    assert build_hf_url("org/model") == "https://huggingface.co/org/model"
    assert build_hf_url("datasets/org/data") == "https://huggingface.co/datasets/org/data"


def test_select_source_default_path() -> None:
    kind, value = select_source(
        path=None, git_url=None, github=None, bitbucket=None, hf=None
    )
    assert kind == "path"
    assert value == Path(".")


def test_select_source_mutual_exclusion() -> None:
    with pytest.raises(SourceError, match="exactly one"):
        select_source(
            path=Path("/tmp/x"),
            git_url="https://example.com/a.git",
            github=None,
            bitbucket=None,
            hf=None,
        )
    with pytest.raises(SourceError, match="exactly one"):
        select_source(
            path=None,
            git_url=None,
            github="o/r",
            bitbucket="w/r",
            hf=None,
        )


def test_select_source_hf() -> None:
    kind, value = select_source(
        path=None, git_url=None, github=None, bitbucket=None, hf="org/model"
    )
    assert kind == "hf"
    assert value == "org/model"


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
        flat = " ".join(" ".join(c) for c in calls)
        assert "ghp_" not in flat
        assert "clone" in flat
        parent = resolved.root.parent
        cleanup_source(resolved)
        assert not resolved.root.exists()
        assert not parent.exists()


def test_clone_failure_raises_source_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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


def test_resolve_bitbucket_and_hf_labels(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BITBUCKET_TOKEN", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)

    def fake_run(args, **kwargs):  # noqa: ANN001
        if "clone" in args:
            Path(args[-1]).mkdir(parents=True, exist_ok=True)
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = ""
        completed.stderr = ""
        return completed

    with patch("repolens.sources.subprocess.run", side_effect=fake_run):
        bb = resolve_source(kind="bitbucket", value="ws/repo", ref=None)
        assert bb.label == "bitbucket:ws/repo"
        cleanup_source(bb)
        hf = resolve_source(kind="hf", value="org/model", ref=None)
        assert hf.label == "hf:org/model"
        cleanup_source(hf)
