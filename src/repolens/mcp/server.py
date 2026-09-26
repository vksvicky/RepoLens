"""Optional MCP server for graph-backed dependency queries (G3).

Install: ``pip install 'repolens-audit[mcp]'`` then configure Cursor/Claude:

```json
{
  "mcpServers": {
    "repolens": {
      "command": "repolens-mcp",
      "args": ["--path", "/absolute/path/to/repo"]
    }
  }
}
```

Tools are millisecond deterministic graph checks — no LLM on the hot path.
Agents are **not** expected to call these before every edit; humans/CI should
run ``repolens check``. Latency budget: local grimp analysis + in-memory BFS.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from repolens.architecture import (
    ArchitectureLoadError,
    discover_architecture_path,
    legal_import_boundaries,
    load_architecture,
)
from repolens.architecture.verify import boundary_for_module, match_boundary
from repolens.config import load_config
from repolens.graph import analyse_python_graph
from repolens.graph.query import (
    check_dependency,
    direct_dependencies,
    direct_dependents,
    reachable_dependencies,
    reachable_dependents,
    would_create_cycle,
)
from repolens.graph.types import GraphResult, GraphStatus


def _load_graph(root: Path) -> GraphResult:
    cfg = load_config(root)
    result = analyse_python_graph(root, config=cfg.graph)
    if result.status in {GraphStatus.FAILED, GraphStatus.SKIPPED}:
        gaps = "; ".join(result.durability_gaps) or result.status.value
        raise RuntimeError(f"Graph unavailable: {gaps}")
    return result


def tool_check_dependency(
    root: Path, *, importer: str, imported: str
) -> dict[str, Any]:
    result = _load_graph(root)
    check = check_dependency(result, importer=importer, imported=imported)
    return {
        "ok": not check.would_create_or_enlarge,
        "wouldCreateOrEnlargeCycle": check.would_create_or_enlarge,
        "cycleModules": list(check.cycle_modules),
        "detail": check.detail,
        "note": (
            "Allow ≠ architectural approval until boundaries are defined (G4). "
            "This tool only checks runtime cycles / reachability."
        ),
    }


def tool_would_create_cycle(
    root: Path, *, importer: str, imported: str
) -> dict[str, Any]:
    result = _load_graph(root)
    check = would_create_cycle(result, importer=importer, imported=imported)
    return {
        "wouldCreateOrEnlargeCycle": check.would_create_or_enlarge,
        "cycleModules": list(check.cycle_modules),
        "detail": check.detail,
    }


def tool_query_dependencies(
    root: Path, *, module: str, transitive: bool = False
) -> dict[str, Any]:
    result = _load_graph(root)
    deps = (
        reachable_dependencies(result, module)
        if transitive
        else direct_dependencies(result, module)
    )
    return {"module": module, "dependencies": deps, "transitive": transitive}


def tool_query_dependents(
    root: Path, *, module: str, transitive: bool = False
) -> dict[str, Any]:
    result = _load_graph(root)
    deps = (
        reachable_dependents(result, module)
        if transitive
        else direct_dependents(result, module)
    )
    return {"module": module, "dependents": deps, "transitive": transitive}


def tool_get_legal_imports(root: Path, *, module: str) -> dict[str, Any]:
    """Post-G4: DSL boundaries ∩ graph facts."""
    arch_path = discover_architecture_path(root)
    if arch_path is None:
        return {
            "module": module,
            "error": "No architecture DSL found (repolens.yaml). Legal imports require G4.",
            "allowedBoundaryNames": [],
            "allowedModulesHint": [],
        }
    try:
        doc = load_architecture(arch_path)
    except ArchitectureLoadError as exc:
        return {"module": module, "error": str(exc), "allowedBoundaryNames": []}

    allowed_names = legal_import_boundaries(module, doc)
    src = boundary_for_module(module, doc)
    # Modules currently in allowed boundaries (from analysed graph).
    result = _load_graph(root)
    allowed_modules: list[str] = []
    if allowed_names:
        name_set = set(allowed_names)
        for edge in result.gated_edges:
            # any module that matches an allowed boundary name
            for b in doc.boundaries:
                if b.name in name_set and match_boundary(edge.imported, b):
                    allowed_modules.append(edge.imported)
        # Also list all known modules in those boundaries (from edges + importers)
        modules: set[str] = set()
        for e in result.gated_edges:
            modules.add(e.importer)
            modules.add(e.imported)
        for m in modules:
            b = boundary_for_module(m, doc)
            if b and b.name in name_set:
                allowed_modules.append(m)
        allowed_modules = sorted(set(allowed_modules))

    return {
        "module": module,
        "boundary": src.name if src else None,
        "allowedBoundaryNames": allowed_names,
        "allowedModulesHint": allowed_modules,
        "architecturePath": str(arch_path),
    }


def build_mcp_server(root: Path) -> Any:
    """Construct an MCP Server instance (requires optional ``mcp`` package)."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit(
            "MCP extra not installed. Run: pip install 'repolens-audit[mcp]'"
        ) from exc

    mcp = FastMCP("repolens")

    @mcp.tool(name="repolens_check_dependency")
    def check_dep(importer: str, imported: str) -> str:
        """Reject if proposed edge creates/worsens a runtime cycle (not architecture approval)."""
        return json.dumps(
            tool_check_dependency(root, importer=importer, imported=imported),
            indent=2,
        )

    @mcp.tool(name="repolens_would_create_cycle")
    def would_cycle(importer: str, imported: str) -> str:
        """Explicit boolean/cycle-group detail for a proposed import edge."""
        return json.dumps(
            tool_would_create_cycle(root, importer=importer, imported=imported),
            indent=2,
        )

    @mcp.tool(name="repolens_query_dependencies")
    def query_deps(module: str, transitive: bool = False) -> str:
        """List modules imported by *module* (reachability only)."""
        return json.dumps(
            tool_query_dependencies(root, module=module, transitive=transitive),
            indent=2,
        )

    @mcp.tool(name="repolens_query_dependents")
    def query_dependents(module: str, transitive: bool = False) -> str:
        """List modules that import *module* (reachability only)."""
        return json.dumps(
            tool_query_dependents(root, module=module, transitive=transitive),
            indent=2,
        )

    @mcp.tool(name="repolens_get_legal_imports")
    def legal_imports(module: str) -> str:
        """G4: list allowed boundary names / module hints from architecture DSL ∩ graph."""
        return json.dumps(tool_get_legal_imports(root, module=module), indent=2)

    return mcp


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="RepoLens MCP server (graph queries)")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("."),
        help="Repository root for graph analysis",
    )
    args = parser.parse_args(argv)
    root = args.path.expanduser().resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        raise SystemExit(2)
    server = build_mcp_server(root)
    server.run()


if __name__ == "__main__":
    main()
