from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EdgeKind(StrEnum):
    RUNTIME = "runtime"
    TYPE_ONLY = "type_only"


class ImportScope(StrEnum):
    MODULE = "module"
    FUNCTION_LOCAL = "function_local"


class GraphStatus(StrEnum):
    OK = "ok"
    SKIPPED = "skipped"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass(frozen=True)
class ImportEdge:
    importer: str
    imported: str
    kind: EdgeKind
    scope: ImportScope
    line: int | None = None
    line_contents: str | None = None


@dataclass(frozen=True)
class CycleGroup:
    modules: tuple[str, ...]  # sorted for stability
    representative_edge: ImportEdge | None = None


@dataclass
class GraphResult:
    status: GraphStatus
    packages: list[str] = field(default_factory=list)
    edges: list[ImportEdge] = field(default_factory=list)
    gated_edges: list[ImportEdge] = field(default_factory=list)
    cycles: list[CycleGroup] = field(default_factory=list)
    cyclicity: int = 0
    module_count: int = 0
    durability_gaps: list[str] = field(default_factory=list)
