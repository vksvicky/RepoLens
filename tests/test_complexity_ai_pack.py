# tests/test_complexity_ai_pack.py
"""C1 — Slow Brain complexity AI pack capped at top_n."""

from __future__ import annotations

from pathlib import Path

from repolens.complexity.ai_pack import (
    format_complexity_ai_section,
    select_complexity_ai_targets,
)
from repolens.complexity.types import FunctionComplexity


def _fn(
    name: str,
    *,
    cyclo: int,
    cog: int,
    path: str = "a.py",
    start: int = 1,
    end: int = 20,
) -> FunctionComplexity:
    return FunctionComplexity(
        name=name,
        path=path,
        start_line=start,
        end_line=end,
        cyclomatic=cyclo,
        cognitive=cog,
    )


def test_select_ai_targets_caps_at_top_n_even_with_many_eligible() -> None:
    funcs = [
        _fn(f"f{i}", cyclo=20 + i, cog=20 + i) for i in range(200)
    ]
    # All have cyclo>=20 → MEDIUM+ eligible (11+)
    selected = select_complexity_ai_targets(funcs, top_n=5)
    assert len(selected) == 5
    # Worst first
    assert selected[0].name == "f199"
    assert selected[4].name == "f195"


def test_select_ai_targets_ignores_clean_functions() -> None:
    funcs = [
        _fn("clean", cyclo=3, cog=2),
        _fn("hot", cyclo=25, cog=30),
    ]
    selected = select_complexity_ai_targets(funcs, top_n=5)
    assert len(selected) == 1
    assert selected[0].name == "hot"


def test_select_ai_targets_hard_max_10() -> None:
    funcs = [_fn(f"f{i}", cyclo=30, cog=30) for i in range(20)]
    selected = select_complexity_ai_targets(funcs, top_n=50)
    assert len(selected) == 10


def test_format_complexity_ai_section_includes_metrics_and_slice(
    tmp_path: Path,
) -> None:
    src = "\n".join(
        [
            "def hot(x):",
            "    if x:",
            "        return 1",
            "    return 0",
        ]
    )
    (tmp_path / "mod.py").write_text(src + "\n", encoding="utf-8")
    target = _fn("hot", cyclo=25, cog=20, path="mod.py", start=1, end=4)
    text = format_complexity_ai_section(tmp_path, [target])
    assert "## Complexity hotspots for AI explanation" in text
    assert "cyclo=25" in text
    assert "cognitive=20" in text
    assert "def hot(x):" in text
    assert "Do not invent metric scores" in text
