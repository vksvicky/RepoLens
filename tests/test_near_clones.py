"""Near-clone heuristic: normalize, physical line map, window hashing (Task 1)."""

from __future__ import annotations

from repolens.heuristics.near_clones import (
    PairHit,
    coalesce_pair_hits,
    iter_windows,
    normalize_lines,
)


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
    # offset = start_b - start_a == +44 for every window → one continuous copy
    hits = [
        PairHit("A.py", "B.py", 1, 12, 45, 56),
        PairHit("A.py", "B.py", 7, 18, 51, 62),
        PairHit("A.py", "B.py", 13, 24, 57, 68),
        PairHit("A.py", "B.py", 19, 30, 63, 74),
    ]
    blocks = coalesce_pair_hits(hits)
    assert len(blocks) == 1
    assert blocks[0].phys_start_a == 1 and blocks[0].phys_end_a == 30
    assert blocks[0].phys_start_b == 45 and blocks[0].phys_end_b == 74


def test_coalesce_rejects_different_offset() -> None:
    # Same A-side stride, but B jumped elsewhere → do NOT merge into one block
    hits = [
        PairHit("A.py", "B.py", 1, 12, 45, 56),
        PairHit("A.py", "B.py", 7, 18, 100, 111),
    ]
    blocks = coalesce_pair_hits(hits)
    assert len(blocks) == 2
