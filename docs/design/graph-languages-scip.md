# Graph languages beyond Python (tree-sitter + SCIP ingest)

Date: 2026-10-06  
Issue: [#95](https://github.com/vksvicky/RepoLens/issues/95)  
Status: Operator contract for the #92–#96 slice. Implementation follows [the spec](../superpowers/specs/2026-10-06-parked-92-96-design.md).

Related: [zugel-comparison-and-roadmap.md](./zugel-comparison-and-roadmap.md) · [complexity-and-cognitive-ai.md](./complexity-and-cognitive-ai.md) · [faq.md](../faq.md)

## What this is

Python stays on **grimp**. Other languages join the **same** SCC / ratchet / architecture-check pipeline as extra edge sources:

1. **tree-sitter** import edges (optional pip extra `[graph]`) for JavaScript, TypeScript, Go, Rust, and C#  
2. **SCIP JSON ingest** (no protobuf, no indexer bundled)  
3. Existing **custom JSON edge array** (`load_precomputed_edges`)

RepoLens does **not** run `scip-typescript` / `scip-python` for you and does **not** replace Sonargraph.

## Install

```bash
pip install "repolens-audit[graph]"
# contributors: pip install -e ".[dev]"  # spec: [dev] includes [graph]
```

Packages: `tree-sitter` + `tree-sitter-language-pack` (Snyk overall Healthy, 2026-10-06). Missing extra: Python graph still runs; non-Python tree-sitter edges are skipped with a durability note.

There is **no** `[complexity]` extra in this slice. Function-span heuristics for those languages use the same `[graph]` parsers.

## Config

```toml
[graph]
tree_sitter = true
extra_edges = ""           # JSON array of {importer, imported, ...}
scip = "graphs/index.json" # SCIP Index JSON (documents + occurrences)
```

Paths are relative to the project root and must stay under that root.

## Relative imports

JS/TS `from "../services/user"` (and equivalent relative Go imports) resolve against the importer’s directory to a **canonical repo-relative path** (`src/services/user.ts`) before the edge is stored. Bare packages stay as specifier strings. SCIP `symbol` strings are not rewritten.

## SCIP JSON shape (supported)

A Sourcegraph **Index** object (camelCase or snake_case):

- `documents[]` with `relative_path` / `relativePath`
- `occurrences[]` with `symbol`, `symbol_roles` / `symbolRoles`, `range`
- Import role bit **`1`**
- `range[0]` is 0-based line; RepoLens stores `line = range[0] + 1`

`imported` is the SCIP **symbol string** (stable). Architecture globs should use path-shaped boundary `path` values for non-Python modules (repo-relative paths), same as today’s slash glob matching.

Binary protobuf `.scip` files are **not** parsed. Convert with Sourcegraph `scip print --json` (or equivalent) outside RepoLens.

## Commands that must see the merged graph

`repolens graph …`, `baseline set`, `check --diff`, `check architecture`, review collect, MCP queries, blast radius, diagnostics.

Entry point after this slice: `analyse_repo_graph` (not Python-only `analyse_python_graph` at those call sites).

## Honesty

| Claim | Allowed |
|-------|---------|
| “JS/TS/Go/Rust/C# imports can feed cycles when `[graph]` is installed” | Yes |
| “Drop in a SCIP JSON dump and we will SCC it” | Yes |
| “We resolve `node_modules` like a bundler / SCIP indexer” | No |
| “Method-level call graph for every language” | No |
| “Tree-sitter replaces grimp for Python” | No |
