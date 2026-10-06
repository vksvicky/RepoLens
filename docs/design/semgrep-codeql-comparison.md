# Semgrep vs CodeQL vs RepoLens (formal study cell)

Date: 2026-10-06  
Issue: [#93](https://github.com/vksvicky/RepoLens/issues/93) (formerly parked under #11)  
Status: Study only — **not** a product feature and **not** a bake-off score.

Related: [repolens-vs-appsec-tools.md](./repolens-vs-appsec-tools.md) · [scanners.md](../scanners.md) · [phase-6.x-scanner-depth-ci-gates-and-credibility.md](./phase-6.x-scanner-depth-ci-gates-and-credibility.md)

## Question this cell answers

Should RepoLens grow a homegrown Semgrep–CodeQL comparison engine, duplicate their rule packs, or pick a winner?

**Answer:** None of those. Keep **both** as optional evidence. RepoLens already runs Semgrep as a plugin and **imports** CodeQL (and other) SARIF. The gap is operator honesty, not another parser.

## What each tool is for

| | Semgrep | CodeQL (GHAS) | RepoLens |
|--|---------|---------------|----------|
| Job | Fast pattern / AST rules you can write and run locally or in CI | Semantic queries with taint/dataflow, usually inside GitHub | Dual-review CLI: scanners + Fast Brain + optional model narrative + architecture gate |
| Strength | Speed, custom rules, low friction, `--oss` path | Interprocedural dataflow, GH PR annotations, query packs | Portable report, explain IDs, cyclicity/architecture, BYOK/local model |
| Weakness | Weaker than CodeQL on deep taint unless rules are expert | GitHub-centric; query authoring cost; private GHAS is paid | Must not claim SAST completeness |
| In RepoLens today | Plugin `semgrep` (`repolens-audit[scanners]` or `plugins install`) | `--import-sarif` / `--require-sarif-import` | Orchestrator |

Naming OWASP themes in a RepoLens playbook does **not** claim CodeQL or Semgrep parity. Playbooks already say that; this study is the comparison cell those playbooks point at.

## Overlap (same bug class, different proof)

| Class | Semgrep (typical) | CodeQL (typical) | RepoLens without those tools |
|-------|-------------------|------------------|------------------------------|
| SQL / command injection | Pattern + some taint rules | Dataflow queries | Heuristic/LLM only — **unverified** unless a scanner or SARIF row exists |
| XSS | Framework-specific rules | DOM/taint queries | Theme `sec.xss_csrf` coverage, not a proof |
| Secrets | Weak vs gitleaks | Secret scanning is a **different** GHAS product | **gitleaks** plugin is the deterministic secrets lane |
| Dependencies | Semgrep Supply Chain (paid/OSS mix) | Dependabot + advisory DB | **OSV** + optional **Trivy**; LLM must not invent CVEs |
| IaC | Limited | Limited | **Checkov** + Trivy misconfig |
| Architecture cycles | No | No | **grimp** / graph + `check architecture` |

When Semgrep and CodeQL both fire on the same sink, RepoLens should **keep both rows** unless an existing SCA-style dedupe key matches (advisory id). Do not invent a Semgrep↔CodeQL fingerprint merger in this slice — SARIF import already preserves tool names.

## What RepoLens must not do

- Ship a “CodeQL lite” query engine or copy GitHub query packs.
- Treat LLM prose as a substitute for either scanner in CI (`scanner_only` / `--fail-on` already exclude LLM from the default gate).
- Claim “we compared Semgrep and CodeQL on N repos and Semgrep wins.” This cell has **no** precision/recall bake-off dataset. If someone runs one later, it belongs under [benchmarks/methodology.md](../benchmarks/methodology.md) with remediation-rate headlines, not F1-only.

## Operator recipe (keep both)

1. Local / generic CI: `repolens plugins install semgrep --yes` and `[scanners] enabled` includes `semgrep`.
2. GitHub: run CodeQL in GHAS or `github/codeql-action`; pass the SARIF into RepoLens:

   ```bash
   repolens review --path . --scanners-only \
     --import-sarif results/codeql.sarif \
     --require-sarif-import
   ```

3. Gate: `--fail-on` / Action `fail-on` on scanner + SARIF rows. Model notes stay off the default scanner-only gate.
4. If CodeQL is absent, say **N/A** in durability / FAQ — do not skip Semgrep to “wait for CodeQL.”

## Recommendation (locked)

| Adopt | Refuse |
|-------|--------|
| Semgrep as the portable SAST plugin | Replacing CodeQL with Semgrep in GitHub-native orgs |
| CodeQL via SARIF import | Bundling CodeQL CLI as a RepoLens plugin (license, size, GH coupling) |
| Honest “use with, not instead of” copy | A scored Semgrep vs CodeQL winner in marketing |
| One study cell (this file) | A sticky tracker that blocks releases |

## Exit for #93

This document on `main`, linked from the docs index, FAQ, and AppSec comparison. No CLI flag named `--compare-semgrep-codeql`.
