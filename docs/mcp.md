# RepoLens MCP (G3)

Optional **secondary** query surface for AI agents. Humans and CI should still run `repolens check` / `repolens check architecture` as the primary gate — agents are **not** expected to call MCP before every edit.

## Install

```bash
pip install 'repolens-audit[mcp]'
```

Entry point: `repolens-mcp`.

## Cursor / Claude config

```json
{
  "mcpServers": {
    "repolens": {
      "command": "repolens-mcp",
      "args": ["--path", "/absolute/path/to/your/repo"]
    }
  }
}
```

## Tools

| Tool | Role |
|------|------|
| `repolens_check_dependency(from, to)` | Reject if the proposed edge creates/worsens a **runtime** cycle. Allow ≠ architectural approval until G4 DSL exists. |
| `repolens_would_create_cycle(from, to)` | Explicit cycle-group detail |
| `repolens_query_dependencies(file)` / `repolens_query_dependents(file)` | Reachability only |
| `repolens_get_legal_imports(file)` | **G4:** DSL `allowed_imports` ∩ analysed modules |

Hot path is deterministic (grimp + in-memory BFS). **No LLM** inside these tools. Latency budget: local graph analysis for the repo root, then millisecond queries.

## Related CLI

- `repolens check --diff` — G2 cyclicity ratchet  
- `repolens check architecture` — G4 boundary verify + FAS candidates  

Design: [zugel-comparison-and-roadmap.md](./design/zugel-comparison-and-roadmap.md).
