# RepoLens vs. Zügel: Architectural Analysis & Upgrade Roadmap

**Status:** Revised 2026-09-06 — corrects inverted MCP/graph ordering and polyglot AST assumptions  
**Tracker:** [#18](https://github.com/vksvicky/RepoLens/issues/18) (umbrella) · [G0 #33](https://github.com/vksvicky/RepoLens/issues/33) · [G1 #34](https://github.com/vksvicky/RepoLens/issues/34) · [G2 #35](https://github.com/vksvicky/RepoLens/issues/35) · [G3 #36](https://github.com/vksvicky/RepoLens/issues/36) · [G4 #37](https://github.com/vksvicky/RepoLens/issues/37)  
**Related:** [architecture-dsl-format-comparison.md](./architecture-dsl-format-comparison.md) · Sonargraph product family ([hello2morrow](https://www.hello2morrow.com/products/sonargraph))

---

## 1. Core Paradigm: Reviewer vs. Guardrail

* **RepoLens** is a **Review CLI / CI Gate**. It acts as a post-facto auditor: humans or agents write code, then RepoLens runs P1→P3 playbooks, orchestrates scanners (Semgrep, OSV, …), and writes Markdown/JSON/SARIF.
* **Zügel** is an **MCP Server** on top of **Sonargraph**. It acts as a real-time guardrail *during* coding: agents ask whether a dependency is legal *before* writing the import.

RepoLens should remain CLI-first. MCP is an optional later surface once deterministic structure exists — not a substitute for it.

## 2. Analytical Depth: Hybrid, Not Adversaries

Earlier drafts framed “LLM heuristics vs deterministic graph math” as opposing camps. The winning formula is **hybrid**:

| Layer | Role | Must not |
|-------|------|----------|
| **Deterministic math** | Detect cycles, measure cyclicity (∑ *n²* over SCCs), enforce hard boundaries | Hallucinate edges or invent imports |
| **LLM agent** | Explain *why* a cycle/boundary breach matters and propose refactoring shapes (interfaces, ports, extract module) | Be the sole detector of structure |

Math finds the tangle; LLMs design the cut. Feeding the **exact cycle subgraph** into the LLM is far more reliable than asking the model to discover cycles from a file dump.

## 3. Rule Definition: Soft Playbooks → Strict DSL (later)

* **Today:** natural-language playbooks (`playbooks/architecture.md`) — accessible, but soft.
* **Zügel / Sonargraph:** Architecture DSL with enforceable allowed/forbidden edges.
* **RepoLens path:** keep playbooks for narrative; add a small `repolens.yaml` (or JSON-Schema-backed YAML) **after** cycles and ratchets work. See [architecture-dsl-format-comparison.md](./architecture-dsl-format-comparison.md).

## 4. Identity: Orchestrator First — Do Not Become Sonargraph

Zügel sits on **15+ years** of Sonargraph static analysis. RepoLens’s strength is **orchestration** (scanners + checklists + LLM reasoning + CI gates).

Writing a full polyglot industrial dependency engine from scratch is a compiler-engineering programme, not a side quest.

**Preferred stance:**

1. **Built-in baseline** — one language MVP (Python *or* TypeScript) with a small in-process import graph.
2. **Open adapters** — ingest external graphs where available (e.g. `pydeps`, `cargo metadata` / depgraph, Sonargraph export, SCIP/LSIF) behind a stable schema.
3. **Tree-sitter / SCIP** — only if/when expanding beyond the MVP language; avoid a sprawl of Node/Java CLIs as hard runtime deps for every user.

---

## What Makes Zügel Effective (Gaps in RepoLens)

### Pre-flight check (`check_proposed_dependency`)
Agents ask “may I import X from Y?” before editing. Requires a **live graph + rules**, not an LLM tool stub.

### Ratchet (cyclicity & baselines)
Cyclicity ≈ ∑ *n²* over strongly connected components (cycle groups). **Debt must not increase** vs a stored baseline. CLI/CI can enforce this without an IDE.

### Adoption ladder
**Cycles-only first**, then layer/DSL rules. Legacy trees drown if you enforce soft P3 architecture before acyclicity.

---

## Critical Blind Spots (Corrected)

### Blind spot 1 — MCP before graph (inverted)

**Flaw:** Exposing `repolens_check_dependency` / `list_legal_imports` before a graph engine exists forces those tools to ask an LLM or return stubs — defeating Zügel-style determinism and adding multi-second latency per call.

**Fix:** Graph engine (and preferably ratchet) **before** MCP.

### Blind spot 2 — Polyglot AST illusion

**Flaw:** “Lightweight AST parsers (`pydeps`, `madge`, native Go…)” understates import resolution: TS path aliases / monorepos / barrels; Python `sys.path` / namespace packages; Rust `mod` / workspace trees. Shelling out to many CLIs bloats the install.

**Fix:** Single-language MVP **or** Tree-sitter / SCIP-style indexes; adapters for external tools as **optional plugins**, not core required deps.

### Blind spot 3 — Tool vs orchestrator

**Flaw:** Competing with Sonargraph’s core engine dilutes RepoLens.

**Fix:** Thin built-in graph + **ingest adapters**; keep orchestration and LLM remediation as the differentiator.

### Blind spot 4 — False dichotomy

**Flaw:** Treating LLM and math as rivals.

**Fix:** Math detects; LLM remediates on the subgraph.

---

## Revised Upgrade Roadmap

| Phase | Do **not** do first | Do this instead |
|-------|---------------------|-----------------|
| **G0** | — | *(Optional parallel)* Cheap Fast Brain quality: near-clones, mega-files, nesting — DRY/KISS signals without a full graph ([Sonargraph lookover](https://www.hello2morrow.com/products/sonargraph)) |
| **G1** | MCP server with empty/LLM-backed tools | **Deterministic graph engine (single-language MVP)** — extract imports, directed graph, Tarjan SCC / cycle groups |
| **G2** | Expand to five languages | **Ratchet & CLI baseline** — `repolens baseline set`, cyclicity ∑*n²*, non-increasing enforcement in CI |
| **G3** | Soft playbook-only enforcement | **`repolens-mcp` guardrail** — `check_proposed_dependency`, `list_legal_imports`, `query_dependents` backed by G1 graph |
| **G4** | Custom `.arc` parser parity | **Architecture DSL + LLM remediation** — `repolens.yaml` boundaries; on violation, pass cycle/edge subgraph to LLM for surgical refactor suggestions |

### G1 — Deterministic graph (MVP)

* Pick **one** ecosystem to start (recommendation: **Python** for RepoLens dogfood, or TypeScript if dogfood targets are JS-heavy).
* In-process extraction preferred over mandatory external CLIs.
* Output: machine-readable cycle list + graph fragment for reports (`source=heuristic` / future `source=graph`).
* Optional: adapter stub that can load a precomputed edge list (for Sonargraph / SCIP later).

**Implementation tip (Python MVP):** Prefer the stdlib `ast` module (`ast.Import`, `ast.ImportFrom`). Resolve internal module paths against the package / src root in pure Python — no third-party runtime dependency required for G1.

### G2 — Ratchet & baseline

```bash
repolens baseline set          # store cyclicity / cycle-group snapshot under .repolens/
repolens review …              # fail CI if cyclicity rises (opt-in flag)
```

Cycles-only mode is the default adoption ladder rung.

**Implementation tip (baselines):** Persist under `.repolens/` in a **deterministic, git-friendly** format (sorted JSON or YAML) containing at least:

* cyclicity score (∑ *n²* over SCCs),
* a stable list of **SCC cycle fingerprints** (e.g. sorted node ids per component, then sorted components),

so teams can optionally **check the baseline into version control** and review ratchet changes in PRs.

### G3 — MCP guardrail

Only after G1 answers dependency queries in milliseconds:

* `repolens_check_dependency(from, to)`
* `repolens_get_legal_imports(file)` (needs G4 rules; until then: “no new cycles” / reachability within component)
* `repolens_query_dependents(file)`

### G4 — DSL + LLM remediation

```yaml
boundaries:
  - name: domain
    path: src/domain/**
    allowed_imports: []
  - name: api
    path: src/api/**
    allowed_imports: [domain]
```

Deterministic verify via graph; LLM receives the **violation subgraph**, not the whole repo, to propose refactors.

### Edge cases & practical nuances

1. **Runtime vs type-only imports (G1):** Modern typed Python often uses:

   ```python
   if TYPE_CHECKING:
       from app.services import OrderService
   ```

   (TypeScript: `import type` is erased at compile time.) These edges do **not** cause runtime `ImportError` cycles. The AST extractor must **tag** each edge as `runtime` or `type_only`.

   * **Runtime cycles** → hard ratchet failure.
   * **Type-only cycles** → configurable (`ignore` | `warn`); default should avoid day-one false-positive floods on typed codebases.

2. **Diff-aware line reporting (G2):** When the ratchet trips in CI, map the regression to the **specific newly introduced `import` line** in the PR/git diff — not only a file-level message. Emit that location in SARIF and/or GitHub Actions annotations, e.g.:

   > PR introduces cyclic dependency: `orders.py` → `billing.py` → `orders.py` (Cyclicity +9)

   anchored on the added `import billing` line in `orders.py`.

3. **Weighted cut hints for the LLM (G4):** For an SCC of 3–5 nodes, the remediation prompt should not treat every edge as equal. Annotate each edge in the violation subgraph with **symbol / usage weight** (e.g. `C → A [1 symbol: StatusEnum]` vs `B → C [25 symbols]`). Prefer inverting or extracting the **lightest** edge (minimum feedback-arc heuristic) so the LLM proposes a minimal-diff cut.

---

## Explicit Non-Goals (Near Term)

* Replacing Sonargraph-Architect / Explorer UI
* Full polyglot industrial resolution in core
* MCP as Phase-1 vanity without graph backing
* Claiming “architecture certified” from LLM-only P3

---

## Conclusion

Zügel shows that **deterministic structure + agent pre-flight** beats post-hoc LLM guessing. RepoLens should:

1. Stay an **orchestrating CLI gate**,
2. Add a **thin, honest graph MVP** (one language + adapters),
3. **Ratchet in CI**,
4. Only then expose **MCP**,
5. Use the **LLM for remediation**, not for discovering cycles.

This ordering preserves credibility and avoids a multi-year compiler side quest.
