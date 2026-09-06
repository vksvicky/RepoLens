# RepoLens vs. Zügel: Architectural Analysis & Upgrade Roadmap

## 1. Core Paradigm: Reviewer vs. Guardrail
*   **RepoLens** is currently a **Review CLI / CI Gate**. It acts as a post-facto auditor. A human or AI writes code, and then RepoLens runs its P1/P2/P3 playbooks, orchestrates scanners (Semgrep, OSV), and generates a comprehensive Markdown report.
*   **Zügel** is an **MCP Server**. It acts as a real-time guardrail *during* the coding process. Because it plugs into an AI agent (via the Model Context Protocol), it actively prevents the agent from making architectural mistakes while the agent is writing the code.

## 2. Analytical Depth: LLM Heuristics vs. Deterministic Graph Math
*   **RepoLens** relies heavily on LLM interpretation of Markdown playbooks (`playbooks/architecture.md`) combined with file-based scanners. While great for general quality and security, LLMs are notoriously bad at holding complex, multi-layered dependency graphs in their context windows.
*   **Zügel** builds a **deterministic dependency model** using graph algorithms. It specifically tracks cyclic dependencies across packages, namespaces, and files. It mathematically knows if an agent just introduced a cycle, whereas RepoLens relies on the LLM "noticing" a bad architectural pattern.

## 3. Rule Definition: Soft Playbooks vs. Strict DSL
*   **RepoLens** uses natural language rules and playbooks. This is highly accessible but leaves room for LLM hallucination or misinterpretation of architectural boundaries.
*   **Zügel** natively understands Sonargraph's Architecture DSL. It has a strict, mathematically enforceable definition of what dependencies are allowed and what aren't.

---

## What Makes Zügel So Effective (The Missing Pieces in RepoLens)

### The "Pre-Flight" Check (`check_proposed_dependency`)
RepoLens waits until the file is saved to run a review. Zügel gives the AI a tool to ask, *"Is it legal for me to import X into Y?"* **before** it even writes the code. If denied, Zügel provides a `list_reachable_components` tool so the AI knows what it *can* use instead. RepoLens lacks this interactive negotiation phase.

### The "Ratchet" (Cyclicity Metric & Baselines)
Zügel introduces a concept called **Cyclicity**. It scores the codebase's tangles (sum of *n²* over cycle groups) and enforces a strict ratchet: **Cyclicity can only go down.** RepoLens tells you what's wrong, but it doesn't have a mathematical baseline to force the AI to say, *"I can't commit this because it increases the cyclicity score."*

### The Adoption Ladder (Cycles First, Architecture Second)
Zügel realizes that most legacy projects can't adopt strict architecture rules on day one. So, it runs in "cycles-only mode" out of the box. Once the codebase is untangled (acyclic), *then* you can define strict rules. RepoLens tries to apply P3 (Architecture) heuristics immediately, which can be overwhelming on a messy codebase.

---

## Upgrade Roadmap: Next Steps for RepoLens

If we want RepoLens to compete with or surpass Zügel's capabilities, here is the proposed architectural roadmap:

### Phase 1: Build the `repolens-mcp` Server
Shift RepoLens into the agent's context window. Build an MCP server wrapper around RepoLens that exposes real-time tools to the AI:
*   `repolens_check_dependency(from_file, to_file)`
*   `repolens_get_legal_imports(file)`
*   `repolens_query_dependents(file)` (Replacing the AI's urge to use `grep` for finding usages).

### Phase 2: Integrate a Deterministic Graph Engine
Stop relying solely on LLMs for Phase 3 (Architecture). Integrate lightweight AST parsers (e.g., `pydeps` for Python, `madge` for JS, or native Go AST parsing).
*   Have RepoLens build a directed graph of imports in memory.
*   Calculate cycles deterministically using standard graph algorithms (e.g., Tarjan's).
*   Feed these mathematically proven cycles to the LLM so it can explain *how* to fix them, rather than asking the LLM to *find* them.

### Phase 3: Implement the "Ratchet"
Add a baseline feature to RepoLens.
```bash
repolens baseline set
```
When a review runs, calculate the number of architectural violations or cyclic dependencies. If the new code increases the score above the baseline, fail the review immediately.

### Phase 4: Formalize the Playbook into a DSL
While `playbooks/architecture.md` is great for human-AI alignment, it is too soft for strict enforcement. Introduce a lightweight `repolens.yaml` (or similar) that defines strict boundaries:
```yaml
boundaries:
  - name: domain
    path: src/domain/**
    allowed_imports: [] # Domain depends on nothing
  - name: api
    path: src/api/**
    allowed_imports: [domain]
```
RepoLens can use the AST graph engine to deterministically verify this YAML before the LLM gets involved.

---
**Conclusion:** Zügel is a masterclass in giving AI strict, mathematical constraints. By giving RepoLens an MCP interface and a deterministic graph engine under the hood, we can bridge the gap between "auditing code after it's written" and "actively guiding the AI while it writes."
