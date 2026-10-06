"""Optional tree-sitter import edges for JS/TS/Go/Rust/C#."""

from __future__ import annotations

from pathlib import Path

from repolens.config import GraphConfig
from repolens.graph.resolve_spec import canonicalize_import
from repolens.graph.types import (
    EdgeKind,
    GraphResult,
    GraphStatus,
    ImportEdge,
    ImportScope,
)
from repolens.inventory import IGNORE_DIR_NAMES
from repolens.path_globs import DEFAULT_REVIEW_SKIP_GLOBS, is_skipped_path

_SUFFIX_LANG = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".mts": "typescript",
    ".cts": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".cs": "c_sharp",
}

_MISSING = (
    "graph.tree_sitter: extra not installed (pip install 'repolens-audit[graph]')"
)


def _language_pack() -> object | None:
    try:
        import tree_sitter_language_pack as pack  # type: ignore[import-untyped]
    except ImportError:
        return None
    return pack


def _iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if any(part in IGNORE_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        rel = path.relative_to(root).as_posix()
        if is_skipped_path(rel, DEFAULT_REVIEW_SKIP_GLOBS):
            continue
        if path.suffix.lower() not in _SUFFIX_LANG:
            continue
        files.append(path)
    return files


def _query_for(lang: str) -> str:
    if lang in {"javascript", "typescript", "tsx"}:
        return """
        (import_statement source: (string) @spec)
        (export_statement source: (string) @spec)
        """
    if lang == "go":
        return """
        (import_spec path: (interpreted_string_literal) @spec)
        """
    if lang == "rust":
        return """
        (use_declaration argument: (scoped_identifier) @spec)
        (use_declaration argument: (identifier) @spec)
        """
    if lang == "c_sharp":
        return """
        (using_directive (qualified_name) @spec)
        (using_directive (identifier) @spec)
        """
    return ""


def _strip_quotes(raw: str) -> str:
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def collect_tree_sitter_edges(root: Path, *, config: GraphConfig) -> GraphResult:
    if not config.tree_sitter:
        return GraphResult(status=GraphStatus.SKIPPED)
    pack = _language_pack()
    if pack is None:
        return GraphResult(status=GraphStatus.SKIPPED)
    files = _iter_source_files(root)
    if not files:
        return GraphResult(status=GraphStatus.SKIPPED)
    try:
        from tree_sitter import Query, QueryCursor  # type: ignore[import-untyped]
    except ImportError:
        return GraphResult(status=GraphStatus.SKIPPED)

    get_parser = getattr(pack, "get_parser", None)
    get_language = getattr(pack, "get_language", None)
    if get_parser is None or get_language is None:
        return GraphResult(status=GraphStatus.SKIPPED)

    edges: list[ImportEdge] = []
    gaps: list[str] = []
    for path in _iter_source_files(root):
        lang = _SUFFIX_LANG[path.suffix.lower()]
        rel = path.relative_to(root).as_posix()
        try:
            parser = get_parser(lang)
            language = get_language(lang)
            source = path.read_bytes()
            tree = parser.parse(source)
            query = Query(language, _query_for(lang))
            cursor = QueryCursor(query)
            captures = cursor.captures(tree.root_node)
        except Exception as exc:  # grammar mismatch is a gap, not a crash
            gaps.append(f"graph.tree_sitter: {rel}: {exc}")
            continue
        nodes = captures.get("spec") if isinstance(captures, dict) else []
        if not nodes:
            continue
        text = source.decode("utf-8", errors="replace")
        for node in nodes:
            spec = _strip_quotes(text[node.start_byte : node.end_byte])
            imported = canonicalize_import(rel, spec, root=root)
            line = int(node.start_point[0]) + 1
            edges.append(
                ImportEdge(
                    importer=rel,
                    imported=imported,
                    kind=EdgeKind.RUNTIME,
                    scope=ImportScope.MODULE,
                    line=line,
                )
            )
    status = GraphStatus.PARTIAL if gaps else GraphStatus.OK
    return GraphResult(
        status=status,
        edges=edges,
        gated_edges=edges,
        durability_gaps=gaps,
        module_count=len({e.importer for e in edges} | {e.imported for e in edges}),
    )
