"""Near-clone heuristic: normalize, physical line map, window hashing (Task 1)."""

from __future__ import annotations

from repolens.heuristics.near_clones import iter_windows, normalize_lines


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
