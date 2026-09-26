"""Load architecture DSL from YAML or JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from repolens.architecture.schema import ArchitectureDoc

DEFAULT_ARCHITECTURE_CANDIDATES = (
    "repolens.yaml",
    "repolens.yml",
    ".repolens/architecture.yaml",
    ".repolens/architecture.yml",
    ".repolens/architecture.json",
    "architecture.json",
)


class ArchitectureLoadError(ValueError):
    """Invalid or missing architecture document."""


def discover_architecture_path(
    root: Path, *, explicit: Path | None = None
) -> Path | None:
    """Resolve architecture DSL path; *explicit* must stay under *root*."""
    root = root.resolve()
    if explicit is not None:
        candidate = explicit.expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            raise ArchitectureLoadError(
                f"Architecture path escapes project root: {explicit}"
            ) from None
        return candidate if candidate.is_file() else None
    for rel in DEFAULT_ARCHITECTURE_CANDIDATES:
        candidate = (root / rel).resolve()
        if candidate.is_file():
            return candidate
    return None


def load_architecture(path: Path) -> ArchitectureDoc:
    raw = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        data = _parse_yaml(raw, path=path)
    elif suffix == ".json":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ArchitectureLoadError(f"Invalid JSON in {path}: {exc}") from exc
    else:
        # Try YAML first, then JSON.
        try:
            data = _parse_yaml(raw, path=path)
        except ArchitectureLoadError:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ArchitectureLoadError(
                    f"Unsupported architecture file {path} (need .yaml/.yml/.json): {exc}"
                ) from exc
    if not isinstance(data, dict):
        raise ArchitectureLoadError(f"Architecture root must be a mapping in {path}")
    try:
        return ArchitectureDoc.model_validate(data)
    except Exception as exc:  # pydantic ValidationError
        raise ArchitectureLoadError(f"Invalid architecture in {path}: {exc}") from exc


def _parse_yaml(raw: str, *, path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ArchitectureLoadError(
            f"Reading {path} requires PyYAML. "
            "Install with: pip install 'repolens-audit[architecture]'"
        ) from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ArchitectureLoadError(f"Invalid YAML in {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ArchitectureLoadError(f"Architecture root must be a mapping in {path}")
    return data
