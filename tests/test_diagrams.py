"""Foolproof Mermaid diagram spine: validate → repair → textual fallback."""

from __future__ import annotations

from unittest.mock import patch

from repolens.diagrams import DiagramResult, process_diagram, validate_mermaid


def test_valid_mermaid_passes() -> None:
    raw = """```mermaid
flowchart LR
  A[Start] --> B[End]
```"""
    result = process_diagram(raw, render_image="never")
    assert result.kind == "mermaid"
    assert "flowchart" in (result.mermaid or "")
    assert result.textual is None
    assert "mermaid_invalid" not in result.notes


def test_invalid_mermaid_repairs_then_falls_back() -> None:
    broken = "```mermaid\nflowchart LR\n  A -->\n```"

    def fake_repair(src: str) -> str:
        return src  # still broken

    with patch("repolens.diagrams.repair_mermaid", side_effect=fake_repair):
        result = process_diagram(broken, render_image="never")
    assert result.kind == "textual"
    assert result.textual
    assert "diagram.mermaid_invalid" in result.notes


def test_repair_can_fix_invalid_mermaid() -> None:
    broken = "```mermaid\nnot a diagram\n```"
    fixed = "flowchart LR\n  A --> B\n"

    with patch("repolens.diagrams.repair_mermaid", return_value=fixed):
        result = process_diagram(broken, render_image="never")
    assert result.kind == "mermaid"
    assert result.mermaid == fixed.strip()


def test_render_failure_keeps_mermaid() -> None:
    raw = "```mermaid\nflowchart LR\n  A --> B\n```"

    def boom(_: str) -> None:
        raise RuntimeError("no mmdc")

    with patch("repolens.diagrams.try_render_image", side_effect=boom):
        result = process_diagram(raw, render_image="always")
    assert result.kind == "mermaid"
    assert result.image_path is None
    assert "diagram.render_skipped" in result.notes


def test_validate_mermaid_rejects_empty() -> None:
    assert validate_mermaid("") is False
    assert validate_mermaid("flowchart LR\n  A --> B\n") is True
