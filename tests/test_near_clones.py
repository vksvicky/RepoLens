"""Near-clone heuristic: normalize, coalesce, suppress, dual caps (Tasks 1–3)."""

from __future__ import annotations

from pathlib import Path

from repolens.heuristics.near_clones import (
    NearClonesConfig,
    PairHit,
    coalesce_pair_hits,
    find_near_clones,
    iter_windows,
    normalize_lines,
)
from repolens.inventory import FileEntry


def _entry(root: Path, relative: str, *, band: int = 3) -> FileEntry:
    path = root / relative
    return FileEntry(
        path=path,
        relative=relative,
        size=path.stat().st_size if path.is_file() else 0,
        priority_band=band,
    )


def _entries_under(root: Path) -> list[FileEntry]:
    paths = sorted(root.rglob("*.py"))
    return [_entry(root, p.relative_to(root).as_posix()) for p in paths if p.is_file()]


def test_normalize_preserves_physical_lines() -> None:
    text = "a = 1\n\nb = 2\n"
    norm, phys = normalize_lines(text)
    assert norm == ["a = 1", "b = 2"]
    assert phys == [1, 3]


def test_issue_line_uses_physical_not_norm_index() -> None:
    # Full find_near_clones tested in Task 3; here window phys_start == first phys line
    text = "x\n\n" + "\n".join(f"line{i}" for i in range(12))
    norm, phys = normalize_lines(text)
    hits = list(iter_windows(norm, phys, window=12, stride=6))
    assert hits[0].phys_start == phys[0]


def test_coalesce_stride_trap_same_offset() -> None:
    # Same normalised A→B offset; overlapping windows → one continuous copy
    hits = [
        PairHit("A.py", "B.py", 1, 12, 45, 56, 0, 12, 44, 56),
        PairHit("A.py", "B.py", 7, 18, 51, 62, 6, 18, 50, 62),
        PairHit("A.py", "B.py", 13, 24, 57, 68, 12, 24, 56, 68),
        PairHit("A.py", "B.py", 19, 30, 63, 74, 18, 30, 62, 74),
    ]
    blocks = coalesce_pair_hits(hits)
    assert len(blocks) == 1
    assert blocks[0].phys_start_a == 1 and blocks[0].phys_end_a == 30
    assert blocks[0].phys_start_b == 45 and blocks[0].phys_end_b == 74


def test_coalesce_rejects_different_offset() -> None:
    # Same A-side stride, but B jumped elsewhere → do NOT merge into one block
    hits = [
        PairHit("A.py", "B.py", 1, 12, 45, 56, 0, 12, 0, 12),
        PairHit("A.py", "B.py", 7, 18, 100, 111, 6, 18, 80, 92),
    ]
    blocks = coalesce_pair_hits(hits)
    assert len(blocks) == 2


def test_coalesce_across_blank_line_physical_gap() -> None:
    """Blank lines between abutting normalised windows must not split a clone.

    Norm windows [0,12) and [12,24) abut. Physical ends/starts skip blanks
    (phys end 12 → next phys start 15), which the old phys+1 check rejected.
    """
    hits = [
        PairHit("A.py", "B.py", 1, 12, 101, 112, 0, 12, 0, 12),
        PairHit("A.py", "B.py", 15, 26, 115, 126, 12, 24, 12, 24),
    ]
    blocks = coalesce_pair_hits(hits)
    assert len(blocks) == 1
    assert blocks[0].phys_start_a == 1 and blocks[0].phys_end_a == 26
    assert blocks[0].phys_start_b == 101 and blocks[0].phys_end_b == 126
    assert blocks[0].occurrences == 2


def test_coalesce_blank_gap_end_to_end(tmp_path: Path) -> None:
    """Copied body with blank lines between stride windows → one finding."""
    # 12 + blanks + 12 non-blank lines; window=12, stride=12 → two abutting
    # normalised windows separated by blanks in physical space.
    part1 = "\n".join(f"x_{i} = {i}" for i in range(12))
    part2 = "\n".join(f"y_{i} = {i}" for i in range(12))
    body = part1 + "\n\n\n" + part2 + "\n"
    (tmp_path / "a.py").write_text(body, encoding="utf-8")
    (tmp_path / "b.py").write_text(body, encoding="utf-8")
    result = find_near_clones(
        _entries_under(tmp_path),
        config=NearClonesConfig(window_lines=12, stride=12),
    )
    assert len(result.issues) == 1, result.issues
    assert result.issues[0].category == "quality.near_clone"


def test_header_comment_suppressed(tmp_path: Path) -> None:
    header = "\n".join(f"# copyright line {i}" for i in range(12))
    (tmp_path / "a.py").write_text(header + "\n", encoding="utf-8")
    (tmp_path / "b.py").write_text(header + "\n", encoding="utf-8")
    result = find_near_clones(_entries_under(tmp_path), config=NearClonesConfig())
    assert result.issues == []


def test_import_only_suppressed(tmp_path: Path) -> None:
    block = "\n".join(f"from typing import A{i}" for i in range(12))
    (tmp_path / "a.py").write_text(block + "\n", encoding="utf-8")
    (tmp_path / "b.py").write_text(block + "\n", encoding="utf-8")
    result = find_near_clones(_entries_under(tmp_path), config=NearClonesConfig())
    assert result.issues == []


def test_dual_cap_emits_ten_and_notes_omission(tmp_path: Path) -> None:
    for i in range(15):
        unique_body = "\n".join(f"value_{i}_{j} = {j}" for j in range(12))
        (tmp_path / f"pair{i}a.py").write_text(unique_body + "\n", encoding="utf-8")
        (tmp_path / f"pair{i}b.py").write_text(unique_body + "\n", encoding="utf-8")
    result = find_near_clones(_entries_under(tmp_path), config=NearClonesConfig())
    assert len(result.issues) <= 10
    assert len(result.issues) == 10
    assert result.cluster_count == 15
    assert any("omitted from findings" in n for n in result.notes)


def test_copied_function_one_finding(tmp_path: Path) -> None:
    body = "\n".join(f"    x = {i}" for i in range(30))
    fn = f"def copied():\n{body}\n"
    leading = "def other():\n    pass\n\n"
    # Shared prefix keeps stride-6 windows aligned; 30-line body coalesces to one block.
    (tmp_path / "a.py").write_text(leading + fn, encoding="utf-8")
    (tmp_path / "b.py").write_text(leading + fn, encoding="utf-8")
    result = find_near_clones(_entries_under(tmp_path), config=NearClonesConfig())
    assert len(result.issues) == 1
    assert result.issues[0].source == "heuristic"
    assert result.issues[0].category == "quality.near_clone"
    assert result.issues[0].line >= 1
