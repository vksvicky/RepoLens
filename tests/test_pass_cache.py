"""Finished deep passes are reused when the packed tree and model match."""

from __future__ import annotations

from pathlib import Path

import pytest

from repolens.inventory import FileEntry
from repolens.pipeline.pass_cache import (
    closure_key,
    load_pass,
    pass_key,
    pass_label,
    save_pass,
)
from repolens.schema import FindingReport, Issue, Severity, Summary


def _entry(root: Path, name: str, text: str) -> FileEntry:
    path = root / name
    path.write_text(text, encoding="utf-8")
    return FileEntry(path=path, relative=name, size=path.stat().st_size, priority_band=3)


def _report() -> FindingReport:
    return FindingReport(
        confidence=80,
        summary=Summary(high=1),
        issues=[
            Issue(
                severity=Severity.HIGH,
                priority="P1",
                category="sec.injection",
                file="app.py",
                line=1,
                title="shell call",
                explanation="Untrusted input reaches a shell.",
                impact="A caller can run a command.",
                recommendedFix="Pass a list of arguments.",
                codeExample="subprocess.run(['ls'])",
            )
        ],
    )


def test_pass_key_changes_when_the_repolens_version_changes(tmp_path: Path) -> None:
    entry = _entry(tmp_path, "app.py", "a = 1\n")
    first = pass_key([entry], "qwen2.5-coder:32b", "p1", version="0.1.0a1")
    second = pass_key([entry], "qwen2.5-coder:32b", "p1", version="0.1.0a2")
    assert first != second


def test_closure_key_changes_when_the_repolens_version_changes() -> None:
    first = closure_key(["sec.injection"], "qwen2.5-coder:32b", version="0.1.0a1")
    second = closure_key(["sec.injection"], "qwen2.5-coder:32b", version="0.1.0a2")
    assert first != second


def test_pass_key_uses_the_installed_repolens_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("repolens.pipeline.pass_cache.__version__", "9.9.9")
    entry = _entry(tmp_path, "app.py", "a = 1\n")
    assert pass_key([entry], "qwen2.5-coder:32b", "p1") == pass_key(
        [entry], "qwen2.5-coder:32b", "p1", version="9.9.9"
    )


def test_pass_key_changes_when_file_contents_change(tmp_path: Path) -> None:
    entry = _entry(tmp_path, "app.py", "a = 1\n")
    first = pass_key([entry], "qwen2.5-coder:32b", "p1")
    entry.path.write_text("a = 2\n", encoding="utf-8")
    second = pass_key([entry], "qwen2.5-coder:32b", "p1")
    assert first != second


def test_closure_key_changes_when_the_missed_ids_change() -> None:
    same = closure_key(["arch.dry", "sec.injection"], "qwen2.5-coder:32b")
    assert same == closure_key(["sec.injection", "arch.dry"], "qwen2.5-coder:32b")
    assert same != closure_key(["arch.dry"], "qwen2.5-coder:32b")
    assert same != closure_key(["arch.dry", "sec.injection"], "other-model")


def test_saved_pass_reloads_the_findings(tmp_path: Path) -> None:
    entry = _entry(tmp_path, "app.py", "a = 1\n")
    key = pass_key([entry], "qwen2.5-coder:32b", "p1")
    save_pass(tmp_path, key, _report())
    loaded = load_pass(tmp_path, key)
    assert loaded is not None
    assert loaded.issues[0].title == "shell call"
    assert pass_label("p1") == "P1 Security"
