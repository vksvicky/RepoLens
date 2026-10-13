"""Freshness guard for the generated docs/learn file notes."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "generate_learn_file_notes.py"
    spec = importlib.util.spec_from_file_location("generate_learn_file_notes", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_exits_zero_when_notes_match_the_tree() -> None:
    module = _load()
    if not (module.LEARN / "src").is_dir():
        pytest.skip("student notes stay on the maintainer machine")
    assert module.main(["--check"]) == 0


def test_check_exits_one_when_a_rendered_note_differs(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load()
    expected = module._rendered_notes()
    dest = next(path for path in expected if path.name != "README.md")
    expected[dest] = expected[dest] + "\n"
    monkeypatch.setattr(module, "_rendered_notes", lambda: expected)
    assert module.main(["--check"]) == 1


def test_write_mode_writes_notes_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load()
    learn = tmp_path / "learn"
    note = learn / "src" / "pkg" / "a.md"
    readme = learn / "src" / "README.md"
    monkeypatch.setattr(module, "LEARN", learn)
    monkeypatch.setattr(
        module,
        "_rendered_notes",
        lambda: {note: "# note\n", readme: "# index\n"},
    )
    assert module.main([]) == 0
    assert note.read_text(encoding="utf-8") == "# note\n"
    assert readme.read_text(encoding="utf-8") == "# index\n"


def test_drift_names_stale_missing_and_extra_notes() -> None:
    module = _load()
    expected = module._rendered_notes()
    stale_path = next(path for path in expected if path.name != "README.md")
    expected[stale_path] = expected[stale_path] + "\n"
    ghost = module.LEARN / "src" / "not-a-real-file.md"
    expected[ghost] = "ghost"
    extra_path = next(
        path for path in list(expected) if path.name != "README.md" and path != stale_path
    )
    del expected[extra_path]

    problems = set(module._drift(expected))

    assert f"stale {stale_path.relative_to(module.ROOT).as_posix()}" in problems
    assert f"missing {ghost.relative_to(module.ROOT).as_posix()}" in problems
    assert f"extra {extra_path.relative_to(module.ROOT).as_posix()}" in problems


def test_source_note_explains_links_and_logic() -> None:
    module = _load()
    note = module._py_note(ROOT / "src" / "repolens" / "adaptive.py")
    assert "No docstring" not in note
    sha = note.split("### `def file_sha256")[1].split("\n### `")[0]
    assert "#### How it links" in sha
    assert "fingerprint_rows_from_entries" in sha
    percentile = note.split("### `def _percentile")[1].split("\n### `")[0]
    assert "#### The logic" in percentile
    assert "ceil" in percentile
    assert "sorted" in percentile
    assert "syntax tree" not in percentile


def test_shared_helpers_are_drawn_in_each_column() -> None:
    module = _load()
    edges = [
        ("apply_llm_consistency", "_mode"),
        ("apply_heuristic_consistency", "_mode"),
        ("apply_llm_consistency", "_apply_demotions"),
        ("_apply_demotions", "_demoted_issue"),
        ("_demoted_issue", "_demote_one"),
    ]
    names = [src for src, _dst in edges] + [dst for _src, dst in edges]
    diagram = module._flow("consistency.py", names, edges)
    assert diagram.splitlines()[1] == "architecture-beta"
    assert ":R --> L:" in diagram
    assert "align " not in diagram
    assert diagram.count("[_mode]") == 2
    assert "group grp1" in diagram
    assert "group grp2" in diagram


def test_file_without_internal_calls_uses_architecture_group() -> None:
    module = _load()
    diagram = module._flow("bands.py", ["rank_issue", "coerce_band"], [])
    assert diagram.splitlines()[1] == "architecture-beta"
    assert "align " not in diagram
    assert "-->" not in diagram
    assert "rank_issue" in diagram
