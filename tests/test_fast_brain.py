"""Phase 6.11: Fast Brain whole-tree heuristics vs LLM inventory cap."""

from __future__ import annotations

from pathlib import Path

from repolens.config import CiConfig, FastBrainConfig
from repolens.heuristics import run_heuristics
from repolens.inventory import scan_inventory
from repolens.pipeline import run_review
from repolens.progress import ReviewProgress
from repolens.schema import Issue, Severity
from repolens.triage import triage_llm_plan


def test_scan_inventory_zero_max_files_uncapped(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"f{i}.py").write_text("x=1\n", encoding="utf-8")
    inv = scan_inventory(tmp_path, max_files=0)
    assert not inv.truncated
    assert len(inv.files) == 5


def test_heuristics_see_files_outside_llm_top_200(tmp_path: Path) -> None:
    # Security-named pads fill the LLM top-200 (band 1); sibling pair is band 3.
    for i in range(200):
        (tmp_path / f"security_pad_{i:04d}.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "ExtractToolView.py").write_text("# a\n", encoding="utf-8")
    (tmp_path / "ReplaceToolView.py").write_text("# b\n", encoding="utf-8")

    fast = scan_inventory(tmp_path, max_files=10_000)
    llm = scan_inventory(tmp_path, max_files=200)
    assert len(llm.files) == 200
    assert len(fast.files) >= 202
    llm_rels = {e.relative for e in llm.files}
    assert "ExtractToolView.py" not in llm_rels
    assert "ReplaceToolView.py" not in llm_rels

    heur = run_heuristics(tmp_path, fast.files, workers=4)
    assert any(
        i.category == "heuristic.sibling_duplication"
        and "ExtractToolView" in (i.file + i.title)
        for i in heur.issues
    )


def test_scanners_only_runs_fast_brain_outside_llm_cap(tmp_path: Path) -> None:
    for i in range(200):
        (tmp_path / f"security_pad_{i:04d}.py").write_text("x=1\n", encoding="utf-8")
    (tmp_path / "ExtractToolView.py").write_text("# a\n", encoding="utf-8")
    (tmp_path / "ReplaceToolView.py").write_text("# b\n", encoding="utf-8")

    result = run_review(
        path=tmp_path,
        mode="sentinel",
        scanners="off",
        scanners_only=True,
        out_dir=tmp_path / "reports",
        fmt="json",
        progress=ReviewProgress(quiet=True),
    )
    assert result.report.provenance is not None
    assert (result.report.provenance.fastBrainFiles or 0) >= 202
    assert result.report.provenance.llmPackFiles == 0
    assert result.files_scanned == result.report.provenance.fastBrainFiles
    assert any(
        i.category == "heuristic.sibling_duplication" for i in result.report.issues
    )


def test_select_pack_entries_includes_fast_brain_only_hits(tmp_path: Path) -> None:
    """Heuristic hit outside Slow Brain top-N must still resolve via Fast Brain."""
    from repolens.inventory import FileEntry
    from repolens.triage import select_pack_entries

    slow = [
        FileEntry(
            path=tmp_path / f"security_pad_{i:04d}.py",
            relative=f"security_pad_{i:04d}.py",
            size=1,
            priority_band=1,
        )
        for i in range(3)
    ]
    outside = FileEntry(
        path=tmp_path / "zzzz_ExtractToolView.py",
        relative="zzzz_ExtractToolView.py",
        size=1,
        priority_band=3,
    )
    fast = [*slow, outside]
    selected = select_pack_entries(fast, ["zzzz_ExtractToolView.py"])
    assert [e.relative for e in selected] == ["zzzz_ExtractToolView.py"]
    assert select_pack_entries(slow, ["zzzz_ExtractToolView.py"]) == []


def test_triage_includes_heuristic_high_hits() -> None:
    heur = Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="heuristic.sibling_duplication",
        file="zzzz_ExtractToolView.py",
        line=1,
        title="Sibling pair",
        explanation="dup",
        impact="Drift risk across parallel implementations.",
        recommendedFix="Consolidate",
        codeExample="# merge",
        source="heuristic",
    )
    plan = triage_llm_plan(
        [],
        available_files=["zzzz_ExtractToolView.py", "other.py"],
        config=CiConfig(triage_routing=True),
        heuristic_issues=[heur],
        include_heuristics=True,
    )
    assert plan.llm_bypassed is False
    assert plan.pack_files == ["zzzz_ExtractToolView.py"]
    assert plan.triage_hits == 1


def test_triage_ignores_heuristics_when_disabled() -> None:
    heur = Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="heuristic.sibling_duplication",
        file="a.py",
        line=1,
        title="Sibling pair",
        explanation="dup",
        impact="Drift risk across parallel implementations.",
        recommendedFix="Consolidate",
        codeExample="# merge",
        source="heuristic",
    )
    plan = triage_llm_plan(
        [],
        available_files=["a.py"],
        config=CiConfig(triage_routing=True),
        heuristic_issues=[heur],
        include_heuristics=False,
    )
    assert plan.llm_bypassed is True


def test_fast_brain_config_defaults() -> None:
    cfg = FastBrainConfig()
    assert cfg.max_files == 10_000
    assert cfg.parallel_workers == 8
    assert cfg.triage_include_heuristics is True
