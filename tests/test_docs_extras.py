"""Docs must list optional-dependencies from pyproject.toml (no silent drift)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
EXTRAS_DOC = ROOT / "docs" / "install-extras.md"

BEGIN = "<!-- BEGIN optional-dependencies -->"
END = "<!-- END optional-dependencies -->"


def _requirement_name(req: str) -> str:
    """Extract distribution name from a PEP 508 requirement string."""
    return re.split(r"[<>=!~;\[]", req, maxsplit=1)[0].strip()


def _optional_deps() -> dict[str, list[str]]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return data["project"]["optional-dependencies"]


def _extras_doc_block() -> str:
    text = EXTRAS_DOC.read_text(encoding="utf-8")
    start = text.find(BEGIN)
    stop = text.find(END)
    assert start != -1, f"{EXTRAS_DOC} missing marker {BEGIN!r}"
    assert stop != -1, f"{EXTRAS_DOC} missing marker {END!r}"
    assert stop > start, "optional-dependencies markers out of order"
    return text[start:stop]


def test_optional_dependencies_documented() -> None:
    block = _extras_doc_block()
    extras = _optional_deps()
    assert extras, "pyproject.toml has no optional-dependencies"

    for extra_name, requirements in extras.items():
        assert f"`{extra_name}`" in block or f"**{extra_name}**" in block, (
            f"Extra [{extra_name}] missing from {EXTRAS_DOC.name} marked block"
        )
        for req in requirements:
            name = _requirement_name(req)
            assert name in block, (
                f"Package {name!r} from [{extra_name}] ({req!r}) missing from "
                f"{EXTRAS_DOC.name} marked block — update the docs or pyproject.toml"
            )


def test_requirement_name_helpers() -> None:
    assert _requirement_name("pytest>=8.0") == "pytest"
    assert _requirement_name("semgrep>=1.100,<2") == "semgrep"
    assert _requirement_name("sentence-transformers>=3.0,<4") == "sentence-transformers"
