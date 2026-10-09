"""Shared architecture DSL fixtures for boundary / quality tests."""

from __future__ import annotations

from pathlib import Path

PACKCYCLE_BOUNDARY_YAML = """
schemaVersion: 1
boundaries:
  - name: a_layer
    path: packcycle/a*
    allowed_imports: []
  - name: b_layer
    path: packcycle/b*
    allowed_imports: [a_layer]
"""


def write_packcycle_with_boundaries(
    root: Path, *, a_import_b: bool = True, noqa: bool = False
) -> Path:
    """Create packcycle a↔b cycle package plus ``repolens.yaml`` under *root*."""
    pkg = root / "packcycle"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    suffix = "  # noqa" if noqa else ""
    if a_import_b:
        (pkg / "a.py").write_text(
            f"from packcycle import b{suffix}\n", encoding="utf-8"
        )
        (pkg / "b.py").write_text(
            f"from packcycle import a{suffix}\n", encoding="utf-8"
        )
    (root / "repolens.yaml").write_text(PACKCYCLE_BOUNDARY_YAML, encoding="utf-8")
    return pkg
