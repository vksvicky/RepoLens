"""Architecture DSL models (G4) — YAML/JSON with pydantic validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class Boundary(BaseModel):
    """One architectural layer / hexagonal ring."""

    name: str = Field(min_length=1)
    # Glob matched against module dotted names rewritten as paths (a.b → a/b)
    # and against dotted module names themselves.
    path: str = Field(min_length=1)
    allowed_imports: list[str] = Field(default_factory=list)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("boundary name must be non-empty")
        return cleaned


class ArchitectureDoc(BaseModel):
    """Root document for ``repolens.yaml`` / ``architecture.json``."""

    schema_version: int = Field(default=1, alias="schemaVersion")
    boundaries: list[Boundary] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @field_validator("boundaries")
    @classmethod
    def _unique_names(cls, value: list[Boundary]) -> list[Boundary]:
        names = [b.name for b in value]
        if len(names) != len(set(names)):
            raise ValueError("boundary names must be unique")
        return value


def architecture_json_schema() -> dict[str, Any]:
    """JSON Schema for IDE autocomplete / docs (draft 2020-12 via pydantic)."""
    return ArchitectureDoc.model_json_schema()
