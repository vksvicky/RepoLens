"""Blast-radius expansion for --git-diff packs."""

from __future__ import annotations

from pathlib import Path

from repolens.blast_radius import expand_blast_radius, expand_blast_radius_paths
from repolens.inventory import FileEntry
from repolens.pipeline.deep_job import DeepJob


def test_expand_blast_radius_disabled_returns_base(tmp_path: Path) -> None:
    paths = expand_blast_radius_paths(
        tmp_path, ["a.py", "b.py"], [], enabled=False
    )
    assert paths == ["a.py", "b.py"]


def test_expand_blast_radius_soft_skips_without_graph(tmp_path: Path) -> None:
    # Empty tree: graph fails; base paths preserved with an honest note.
    result = expand_blast_radius(
        tmp_path, ["src/repolens/cli/app.py"], [], enabled=True
    )
    assert result.paths == ["src/repolens/cli/app.py"]
    assert result.note
    assert "blast-radius skipped" in result.note


def test_filter_entries_blast_radius() -> None:
    from repolens.blast_radius import filter_entries_blast_radius

    a = FileEntry(path=Path("a.py"), relative="a.py", size=1, priority_band=1)
    b = FileEntry(path=Path("b.py"), relative="b.py", size=1, priority_band=1)
    assert [e.relative for e in filter_entries_blast_radius([a, b], ["b.py"])] == ["b.py"]


def test_expand_blast_radius_adds_neighbours(tmp_path: Path, monkeypatch) -> None:
    from types import SimpleNamespace

    from repolens.blast_radius import expand_blast_radius
    from repolens.graph.types import EdgeKind, GraphStatus, ImportEdge, ImportScope

    src = tmp_path / "pkg"
    src.mkdir()
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "a.py").write_text("from pkg import b\n", encoding="utf-8")
    (src / "b.py").write_text("x = 1\n", encoding="utf-8")
    entries = [
        FileEntry(path=src / "a.py", relative="pkg/a.py", size=1, priority_band=1),
        FileEntry(path=src / "b.py", relative="pkg/b.py", size=1, priority_band=1),
    ]

    class FakeResult:
        status = GraphStatus.OK
        durability_gaps: list[str] = []
        gated_edges = [
            ImportEdge(
                importer="pkg.a",
                imported="pkg.b",
                kind=EdgeKind.RUNTIME,
                scope=ImportScope.MODULE,
            )
        ]

    monkeypatch.setattr(
        "repolens.graph.build.analyse_python_graph",
        lambda root, config=None: FakeResult(),
    )
    monkeypatch.setattr(
        "repolens.config.load_config",
        lambda root: SimpleNamespace(graph=None),
    )
    result = expand_blast_radius(tmp_path, ["pkg/a.py"], entries, enabled=True)
    assert "pkg/a.py" in result.paths
    assert "pkg/b.py" in result.paths
    assert result.note and "added" in result.note


def test_module_path_helpers_roundtrip() -> None:
    from repolens.blast_radius import _module_to_candidates, _rel_to_module

    assert _rel_to_module("src/repolens/cli/app.py") == "src.repolens.cli.app"
    assert "src/repolens/cli/app.py" in _module_to_candidates("src.repolens.cli.app")


def test_change_set_covers_arch_blast_radius() -> None:
    from types import SimpleNamespace

    from repolens.blast_radius import blast_radius_coverage_seeds
    from repolens.coverage import evaluate_coverage

    _na, covered = blast_radius_coverage_seeds(
        full_audit=False,
        change_set=SimpleNamespace(base="HEAD", pathCount=2, note="blast-radius added 1"),
    )
    result = evaluate_coverage(
        ["arch.blast_radius"], [], [], seeded_na={}, seeded_covered=covered
    )
    assert result.missed == []
    assert result.covered == ["arch.blast_radius"]
    note = result.covered_notes["arch.blast_radius"]
    assert "HEAD" in note
    assert "2" in note


def test_missing_change_set_is_concrete_na() -> None:
    from repolens.blast_radius import blast_radius_coverage_seeds
    from repolens.coverage import evaluate_coverage, is_lazy_na_reason

    na, covered = blast_radius_coverage_seeds(full_audit=False, change_set=None)
    result = evaluate_coverage(
        ["arch.blast_radius"], [], [], seeded_na=na, seeded_covered=covered
    )
    assert result.missed == []
    reason = result.na["arch.blast_radius"]
    assert "git change-set" in reason
    assert is_lazy_na_reason(reason) is False
    full_na, _full_covered = blast_radius_coverage_seeds(full_audit=True, change_set=None)
    assert "full audit" in full_na["arch.blast_radius"]


def test_project_seed_wins_over_blast_radius_fact() -> None:
    from types import SimpleNamespace

    from repolens.blast_radius import merge_blast_radius_coverage_seeds

    na, covered = merge_blast_radius_coverage_seeds(
        {"arch.blast_radius": "desktop app; out of scope"},
        {},
        full_audit=False,
        change_set=SimpleNamespace(base="main", pathCount=1, note=""),
    )
    assert na["arch.blast_radius"] == "desktop app; out of scope"
    assert "arch.blast_radius" not in covered


def test_deep_llm_forwards_change_set() -> None:
    from unittest.mock import MagicMock, patch

    from repolens.pipeline.run_support import _invoke_deep_llm

    state = MagicMock()
    state.report_when = "already"
    block = object()
    state.change_set_block = block
    with patch("repolens.pipeline.deep_exec._analyze_deep_passes") as analyze:
        _invoke_deep_llm(state)
    assert analyze.call_args.args[0].change_set is block


def test_coverage_closure_keeps_blast_radius_answer(tmp_path: Path) -> None:
    from unittest.mock import MagicMock, patch

    from repolens.config import RepoLensConfig
    from repolens.coverage import CoverageResult
    from repolens.pipeline.deep_exec_coverage import _run_coverage_closure_if_needed
    from repolens.schema import FindingReport, Summary

    report = FindingReport(confidence=80, summary=Summary())
    coverage = CoverageResult(missed=["sec.injection"])
    with (
        patch("repolens.llm.model_lock.bind_lock_context", return_value="tok"),
        patch("repolens.llm.model_lock.reset_lock_context"),
        patch("repolens.pipeline.deep_pass._apply_coverage_closure", return_value=report),
        patch("repolens.pipeline.pass_resume.snapshot_finished"),
    ):
        _report, after = _run_coverage_closure_if_needed(DeepJob(
            report=report,
            coverage=coverage,
            unique_ids=["arch.blast_radius", "sec.injection"],
            cfg=RepoLensConfig(),
            prog=MagicMock(),
            raw_dir=tmp_path,
            root=tmp_path,
            parts=[],
            heur_issues=[],
            finished_labels=[],
            out_dir=None,
            fmt="md",
            mode="review",
            report_when=None,
            full_audit=False,
            change_set=None,
        ))
    assert "arch.blast_radius" not in after.missed
    assert "arch.blast_radius" in after.na
