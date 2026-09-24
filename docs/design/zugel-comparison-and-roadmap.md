# RepoLens vs. Zügel: Architectural Analysis & Upgrade Roadmap

**Status:** Revised 2026-09-24 — adds grimp-first Python resolution, CLI-primary guardrails, FAS-as-candidate (not gospel)  
**Prior revision:** 2026-09-06 — inverted MCP/graph ordering and polyglot AST assumptions  
**Tracker:** [#18](https://github.com/vksvicky/RepoLens/issues/18) (umbrella) · [G0 #33](https://github.com/vksvicky/RepoLens/issues/33) · [G1 #34](https://github.com/vksvicky/RepoLens/issues/34) · [G2 #35](https://github.com/vksvicky/RepoLens/issues/35) · [G3 #36](https://github.com/vksvicky/RepoLens/issues/36) · [G4 #37](https://github.com/vksvicky/RepoLens/issues/37)  
**Related:** [architecture-dsl-format-comparison.md](./architecture-dsl-format-comparison.md) · Sonargraph product family ([hello2morrow](https://www.hello2morrow.com/products/sonargraph))

---

## 1. Core Paradigm: Reviewer vs. Guardrail

* **RepoLens** is a **Review CLI / CI Gate**. It acts as a post-facto auditor: humans or agents write code, then RepoLens runs P1→P3 playbooks, orchestrates scanners (Semgrep, OSV, …), and writes Markdown/JSON/SARIF.
* **Zügel** is an **MCP Server** on top of **Sonargraph**. It acts as a real-time guardrail *during* coding in an ecosystem where Sonargraph already sits in the IDE workspace.

RepoLens should remain **CLI-first**. The primary cycle/architecture gate is a **fast local check** (CI job, `repolens check --diff`, optional pre-commit) returning anchored diagnostics. MCP is a **secondary query surface** for agents that already poll tools — not the thing we rely on to stop every import before it is typed.

## 2. Analytical Depth: Hybrid, Not Adversaries

Earlier drafts framed “LLM heuristics vs deterministic graph math” as opposing camps. The winning formula is **hybrid**:

| Layer | Role | Must not |
|-------|------|----------|
| **Deterministic math** | Detect cycles, measure cyclicity (∑ *n²* over SCCs), enforce hard boundaries | Hallucinate edges or invent imports |
| **LLM agent** | Explain *why* a cycle/boundary breach matters and propose refactoring shapes (interfaces, ports, extract module) | Be the sole detector of structure; blindly trust a minimal cut |

Math finds the tangle; LLMs design the cut **with domain judgment**. Feeding the **exact cycle subgraph** (plus weights and layer labels) into the LLM is far more reliable than asking the model to discover cycles from a file dump.

## 3. Rule Definition: Soft Playbooks → Strict DSL (later)

* **Today:** natural-language playbooks (`playbooks/architecture.md`) — accessible, but soft.
* **Zügel / Sonargraph:** Architecture DSL with enforceable allowed/forbidden edges.
* **RepoLens path:** keep playbooks for narrative; add a small `repolens.yaml` (or JSON-Schema-backed YAML) **after** cycles and ratchets work. See [architecture-dsl-format-comparison.md](./architecture-dsl-format-comparison.md).

## 4. Identity: Orchestrator First — Do Not Become Sonargraph

Zügel sits on **15+ years** of Sonargraph static analysis. RepoLens’s strength is **orchestration** (scanners + checklists + LLM reasoning + CI gates).

Writing a full polyglot industrial dependency engine from scratch is a compiler-engineering programme, not a side quest. Even **Python-only** import resolution is a multi-year pit if done naively with `ast.parse`.

**Preferred stance:**

1. **Python MVP via a battle-tested resolver** — prefer adopting/wrapping **[grimp](https://github.com/seddonym/grimp)** (engine behind [import-linter](https://github.com/seddonym/import-linter)) rather than inventing path resolution; keep our SCC/ratchet/report layer on top.
2. **Open adapters** — ingest external graphs where available (Sonargraph export, SCIP/LSIF, `cargo metadata`, …) behind a stable schema.
3. **Tree-sitter / SCIP** — only if/when expanding beyond Python; avoid a sprawl of Node/Java CLIs as core required deps.

---

## What Makes Zügel Effective (Gaps in RepoLens)

### Structural detection + enforcement
Deterministic cycles and (later) layer rules. RepoLens still leans on soft P3 LLM narrative here.

### Ratchet (cyclicity & baselines)
Cyclicity ≈ ∑ *n²* over strongly connected components (cycle groups). **Debt must not increase** vs a stored baseline. CLI/CI can enforce this without an IDE — this is the guardrail that actually matches how humans and agents work.

### Adoption ladder
**Cycles-only first**, then layer/DSL rules. Legacy trees drown if you enforce soft P3 architecture before acyclicity.

### Pre-flight MCP (secondary)
Zügel’s “ask before import” works because Sonargraph already owns the workspace. Treat MCP queries as optional agent convenience **after** CLI diagnostics exist — not as the primary prevention story.

---

## Critical Blind Spots (Corrected)

### Blind spot 1 — MCP before graph (inverted)

**Flaw:** Exposing `repolens_check_dependency` / `list_legal_imports` before a graph engine exists forces those tools to ask an LLM or return stubs — defeating Zügel-style determinism and adding multi-second latency per call.

**Fix:** Graph engine (and preferably ratchet + CLI check) **before** MCP.

### Blind spot 2 — Polyglot AST illusion

**Flaw:** “Lightweight AST parsers (`pydeps`, `madge`, native Go…)” understates import resolution: TS path aliases / monorepos / barrels; Python `sys.path` / namespace packages; Rust `mod` / workspace trees. Shelling out to many CLIs bloats the install.

**Fix:** Single-language MVP **or** Tree-sitter / SCIP-style indexes; adapters for external tools as **optional plugins**, not core required deps.

### Blind spot 3 — Tool vs orchestrator

**Flaw:** Competing with Sonargraph’s core engine dilutes RepoLens.

**Fix:** Proven Python resolver (grimp) + **ingest adapters**; keep orchestration and LLM remediation as the differentiator.

### Blind spot 4 — False dichotomy

**Flaw:** Treating LLM and math as rivals.

**Fix:** Math detects; LLM remediates on the subgraph (with domain judgment).

### Blind spot 5 — “stdlib `ast` is enough” (Python G1)

**Flaw:** Pure `ast.Import` / `ast.ImportFrom` + “resolve against src root” understates real Python:

* Relative imports (`from . import foo`, `from ..bar import baz`) need package-layout tracking.
* Function-local / lazy imports (`def get_billing(): from app import billing`) are often **intentional** cycle breakers at import time — treating them as hard edges floods false positives.
* Name collisions between local packages and site-packages.
* `TYPE_CHECKING` aliases (`as TC`), `typing.TYPE_CHECKING`, `if not TYPE_CHECKING:` break naive AST guards.

**Fix:** Do **not** write Python import resolution from scratch for G1. Study/adopt **grimp** (or equivalent battle-tested library). Own the cycle metric, baseline, report, and CLI gate; borrow the hard resolution work.

### Blind spot 6 — MCP as primary pre-flight guardrail

**Flaw:** Expecting Cursor / Claude Code / Cline / Copilot agents to call MCP **before every import** is unrealistic: high token/latency cost, weak system-prompt compliance. Agents typically **write → linter/CI → read diagnostics → fix**. Zügel’s workflow assumes Sonargraph already in the IDE loop.

**Fix:** Primary gate = **`repolens check --diff`** (or equivalent) in CI / pre-commit with anchored line diagnostics. MCP = secondary query API for agents that already use tools — never the only enforcement path.

### Blind spot 7 — “Minimal FAS cut = best architecture”

**Flaw:** A weighted feedback-arc set optimises for **fewest/lightest edges**, not Clean/Hexagonal direction. Example: domain `OrderService` → infra `AuditLog` (1 symbol) vs `AuditLog` → domain (20 symbols). Math prefers cutting the domain→infra edge; good architecture often prefers ports/events and **keeping** domain free of infra inversion hacks.

**Fix:** Present FAS (and weights) as **candidate cut options** plus symbol breakdown and optional layer labels (`domain` / `ports` / `adapters`). Let the LLM evaluate dependency **direction** against stated principles — not rubber-stamp the mathematical minimum.

---

## Revised Upgrade Roadmap

| Phase | Do **not** do first | Do this instead |
|-------|---------------------|-----------------|
| **G0** | — | *(Optional parallel)* Cheap Fast Brain quality: near-clones, mega-files, nesting — DRY/KISS signals without a full graph |
| **G1** | Hand-rolled `ast` path resolver; MCP stubs | **Deterministic graph (Python MVP)** via **grimp** (or equal) + Tarjan SCC / cycle groups + edge tags |
| **G2** | Expand to five languages | **Ratchet & CLI baseline** + **`repolens check --diff`** (primary gate) |
| **G3** | MCP-as-only-guardrail | **Optional `repolens-mcp`** query surface backed by G1 — secondary to CLI/CI |
| **G4** | Blind “cut lightest FAS edge” | **Architecture DSL + LLM remediation** — FAS as candidate; domain direction wins |

### G1 — Deterministic graph (MVP)

* Ecosystem: **Python** for RepoLens dogfood (TypeScript later via adapter, not day-one polyglot).
* Prefer **grimp** (or documented equivalent) for import graph construction; wrap behind a thin RepoLens interface so we can swap adapters.
* Tag edges as **`runtime`** vs **`type_only`** (and document policy for **function-local** imports: default exclude from hard cycles or severity-cap — configurable).
* Output: machine-readable cycle list + graph fragment for reports (`source=graph` / heuristic).
* Optional: adapter stub for precomputed edge lists (Sonargraph / SCIP later).

**Implementation tip:** Evaluate grimp licence/deps against RepoLens MIT packaging (`repolens-audit` optional extra or core — decide in the G1 plan). Do not ship a naive `ast`-only resolver as “done.”

### G2 — Ratchet, baseline & CLI check (primary gate)

```bash
repolens baseline set              # store cyclicity / SCC fingerprints under .repolens/
repolens check --diff              # or review flag: fail if runtime cyclicity rises vs baseline
# wire into CI + optional pre-commit
```

Cycles-only mode is the default adoption ladder rung.

**Implementation tip (baselines):** Persist under `.repolens/` in a **deterministic, git-friendly** format (sorted JSON or YAML) containing at least:

* cyclicity score (∑ *n²* over SCCs),
* a stable list of **SCC cycle fingerprints** (e.g. sorted node ids per component, then sorted components),

so teams can optionally **check the baseline into version control** and review ratchet changes in PRs.

**Diff-aware reporting:** When the ratchet trips, map the regression to the **specific newly introduced `import` line** in the PR/git diff. Emit SARIF and/or GitHub Actions annotations.

### G3 — MCP as secondary query surface

Only after G1 answers dependency queries in milliseconds **and** G2 CLI/CI check exists.

**Pre-G4 tools** (no boundary DSL yet — do **not** claim “legal imports”):

* `repolens_check_dependency(from, to)` — would this edge create/enlarge a **runtime** cycle? (optional: violate stored G2 baseline)
* `repolens_would_create_cycle(from, to)` — explicit boolean/cycle-group detail
* `repolens_query_dependents(file)` / `repolens_query_dependencies(file)` — reachability only

**Post-G4 only:**

* `repolens_get_legal_imports(file)` — DSL boundaries ∩ graph facts.

Document clearly: agents are **not** expected to call these before every edit; humans/CI should run `repolens check`. MCP helps agents that already tool-call when investigating a failure.

### G4 — DSL + LLM remediation (FAS = candidate)

```yaml
boundaries:
  - name: domain
    path: src/domain/**
    allowed_imports: []
  - name: api
    path: src/api/**
    allowed_imports: [domain]
```

Deterministic verify via graph; LLM receives the **violation subgraph**, not the whole repo.

Provide:

1. Verified **weighted feedback-arc set(s)** as candidate cut options (must break every cycle),
2. Per-edge **symbol / usage weights**,
3. Optional **layer / hexagonal hints** (domain must not depend on adapters),

and ask the LLM to choose a cut that respects architecture — not merely the lightest edge.

### Edge cases & practical nuances

1. **Runtime vs type-only imports (G1):** Prefer resolver support + explicit tags. Example shape:

   ```python
   from typing import TYPE_CHECKING

   if TYPE_CHECKING:
       from app.services import OrderService
   ```

   Also handle aliases (`TYPE_CHECKING as TC`), `typing.TYPE_CHECKING`, and negated guards in policy docs even if the library does the heavy lifting.

   * **Runtime cycles** → hard ratchet failure.
   * **Type-only cycles** → configurable (`ignore` | `warn`).
   * **Function-local imports** → configurable; default should not treat intentional lazy imports as Critical cycle noise.

2. **Diff-aware line reporting (G2):** Anchor CI failures on the new import line (SARIF / annotations).

3. **Weighted FAS + domain direction (G4):** FAS verifies cycle-breaking; **architecture** chooses which valid set to apply. Never present “min weight alone” as the refactoring answer.

---

## Explicit Non-Goals (Near Term)

* Replacing Sonargraph-Architect / Explorer UI
* Full polyglot industrial resolution in core
* MCP as Phase-1 vanity or as the **only** enforcement path
* Hand-rolled Python import resolver as a “temporary” core forever
* Claiming “architecture certified” from LLM-only P3 or from FAS weight alone

---

## Conclusion

Zügel shows that **deterministic structure + enforcement** beats post-hoc LLM guessing. For RepoLens:

1. Stay an **orchestrating CLI gate**,
2. Build Python graph honesty via **grimp (or equal)**, not naive `ast`,
3. Enforce with **`repolens check` / CI / pre-commit** (primary) and ratchet baselines,
4. Offer **MCP as optional** agent queries,
5. Use the **LLM for remediation** with FAS candidates + domain direction — not for discovering cycles or rubber-stamping minimal cuts.

This ordering preserves credibility and avoids both a compiler side quest and an MCP-workflow fantasy.
