"""Excerpt and FTS reads stop after max_chars + 1."""

from __future__ import annotations

from pathlib import Path

import pytest

from repolens.inventory import FileEntry, read_excerpt, read_prefix
from repolens.pipeline.prompt import _append_source_files


class _Handle:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.sizes: list[int] = []

    def read(self, size: int = -1) -> str:
        self.sizes.append(size)
        if size < 0:
            return self.payload
        return self.payload[:size]

    def __enter__(self) -> _Handle:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


def test_excerpt_requests_one_past_the_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    handle = _Handle("a" * 20_000)
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: handle)
    entry = FileEntry(path=tmp_path / "a.py", relative="a.py", size=20_000, priority_band=1)
    text = read_excerpt(entry)
    assert handle.sizes == [12_001]
    body, _sep, _rest = text.partition("\n\n/*")
    assert body == "a" * 12_000
    assert "truncated by RepoLens" in text


def test_fts_prefix_requests_one_past_eighty_thousand(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handle = _Handle("b" * 100_000)
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: handle)
    text = read_prefix(tmp_path / "a.py", 80_000)
    assert handle.sizes == [80_001]
    assert len(text) == 80_001


def test_append_source_files_includes_the_prompt_once(tmp_path: Path) -> None:
    path = tmp_path / "a.py"
    path.write_text("print(1)\n", encoding="utf-8")
    entry = FileEntry(path=path, relative="a.py", size=path.stat().st_size, priority_band=1)
    text = _append_source_files("UNIQUE_PROMPT_TOKEN", [entry])
    assert text.count("UNIQUE_PROMPT_TOKEN") == 1
    assert "## Source files" in text
    assert "print(1)" in text
