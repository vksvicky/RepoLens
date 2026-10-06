"""Architecture DSL models (G4) — YAML/JSON with pydantic validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return str(value)


class Boundary(BaseModel):
    """One architectural layer / hexagonal ring."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(min_length=1)
    # Glob matched against module dotted names rewritten as paths (a.b → a/b)
    # and against dotted module names themselves.
    path: str = Field(min_length=1)
    allowed_imports: list[str] = Field(default_factory=list)
    forbidden_imports: list[str] = Field(default_factory=list)
    description: str | None = None

    @field_validator("name", "path", mode="before")
    @classmethod
    def _strip_str(cls, value: Any) -> str:
        cleaned = _stringify(value).strip()
        if not cleaned:
            raise ValueError("must be a non-empty string")
        return cleaned

    @field_validator("allowed_imports", "forbidden_imports", mode="before")
    @classmethod
    def _str_names(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("must be a list of boundary names")
        out: list[str] = []
        for item in value:
            name = _stringify(item).strip()
            if name:
                out.append(name)
        return out


class ArchitectureDoc(BaseModel):
    """Root document for ``repolens.yaml`` / ``architecture.json``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    json_schema_url: str | None = Field(default=None, alias="$schema")
    schema_version: int = Field(default=1, alias="schemaVersion")
    strict: bool = False
    boundaries: list[Boundary] = Field(default_factory=list)

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
