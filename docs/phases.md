# RepoLens — Implementation phases

Track what is planned, in progress, and done. Update checkboxes as work lands.  
For release notes aimed at users, also update [CHANGELOG.md](./CHANGELOG.md).

**Product name:** RepoLens  
**Security-only mode:** `repolens sentinel`  
**Full review mode:** `repolens review` (P1 → P2 → P3)  
**Current phase:** Phase 2 in progress (multi-source MVP — 2026-08-04)  
**CLI language:** Python 3.11+

---

## Legend

| Status | Meaning |
|--------|---------|
| `[ ]` | Not started |
| `[~]` | In progress (note in “Notes”) |
| `[x]` | Done |

---

## Phase 0 — Foundation (open source + playbooks)

**Goal:** Anyone can adopt the review process and follow the project before the CLI exists.

| Item | Status | Notes |
|------|--------|-------|
| Repository created and published | [x] | https://github.com/vksvicky/RepoLens |
| User-friendly README | [x] | |
| This phases tracker (`docs/phases.md`) | [x] | Renamed from `PHASES.md`; lives under `docs/` |
| Docs under `docs/`; root keeps `README` + `LICENSE` | [x] | Community health files in `docs/` (GitHub-supported) |
| Security playbook vendored | [x] | `playbooks/security.md` |
| Architecture playbook vendored | [x] | `playbooks/architecture.md` |
| Docs: using playbooks without CLI | [x] | `docs/using-playbooks.md` |
| Docs index + naming pattern explained | [x] | `docs/README.md` |
| MIT LICENSE | [x] | Root |
| CONTRIBUTING / CODE_OF_CONDUCT / SECURITY / SUPPORT / CHANGELOG | [x] | Under `docs/` with conventional filenames |
| GitHub issue / PR templates | [x] | `.github/` |
| Placeholder CI workflow | [x] | Docs / lint later |
| Choose implementation language (Python vs TypeScript) | [x] | **Python 3.11+** — see design doc + FAQ |
| Design spec for CLI UX & report schema | [x] | `docs/design/cli-and-report-schema.md` |
| FAQ (incl. target languages / tools) | [x] | `docs/faq.md` |
| ADR-01 analysis runtime + diagram legend | [x] | `docs/adr/` (Mermaid HLD / sequence / zones) |
| Remote published (`vksvicky/RepoLens`) | [x] | https://github.com/vksvicky/RepoLens |

**Phase 0 exit criteria:** Docs + playbooks + community files on `main`; language/design decided. → **Met (2026-08-04).**

---

## Phase 1 — Core CLI (local only)

**Goal:** `repolens review` and `repolens sentinel` work on a local `--path`.

| Item | Status | Notes |
|------|--------|-------|
| Package scaffold + `repolens` entrypoint | [x] | `pyproject.toml`, `src/repolens`, console script |
| Config file (`~/.config/repolens/` or project `.repolens.toml`) | [x] | + `REPOLENS_*` env overlay |
| First-run UX: BYOK vs Ollama vs scanners-only | [x] | `repolens init --provider ...` |
| Cloud + local (Ollama) provider adapters | [x] | OpenAI-compatible + Anthropic + Ollama |
| Load playbooks from `playbooks/` | [x] | Package data + checkout fallback |
| `repolens sentinel` — security-only (P1) | [x] | |
| `repolens review` — P1 → P2 → P3 on local tree/diff | [x] | `--mode full|diff`, `--full-audit` |
| Finding schema: severity, impact, fix, codeExample (required Critical/High) | [x] | Pydantic validators |
| OWASP/CWE tags on LLM findings (best-effort) | [x] | Optional `owasp` / `cwe` fields |
| Confidence % in summary | [x] | CLI table + Markdown |
| Write `reports/gate_review_report_YYYY-MM-DD.md` | [x] | + JSON via `--format` |
| `repolens export` (Markdown path; PDF if pandoc present) | [x] | |
| Unit/integration tests (TDD) for report writer & CLI args | [x] | pytest in CI |
| User docs: install + first review + AI key FAQ | [x] | README quick start + setup guide + CONTRIBUTING |
| Setup guide: cloud / Ollama / scanners-only | [x] | `docs/setup-ai-and-scanners.md` (CLI alpha) |

**Phase 1 exit criteria:** Local full + sentinel reviews produce Markdown reports with mandatory Critical/High code examples; tests green in CI.

---

## Phase 2 — Multi-source ingest

**Goal:** Review repos that are not already on disk.

| Item | Status | Notes |
|------|--------|-------|
| Generic `--git-url` (+ `--ref`) shallow clone to temp | [x] | Cleanup after run |
| `--github owner/repo` | [x] | `GITHUB_TOKEN`/`GH_TOKEN` then `gh auth token` |
| `--bitbucket workspace/repo` | [ ] | Deferred Phase 2.1 |
| `--hf` Hugging Face Hub git repos | [ ] | Deferred Phase 2.1 |
| Size limits / ignore globs / P1 file prioritization | [x] | Reuses Phase 1 inventory |
| Docs: auth for each host | [x] | `docs/remote-sources.md` (GitHub + git-url) |

**Phase 2 exit criteria:** Same commands work for local and at least GitHub + generic git URL; secrets never logged. → **MVP met (2026-08-04)** for `--git-url` + `--github`; Bitbucket/HF remain open.

---

## Phase 3 — Durability plugins (optional analyzers)

**Goal:** Merge deterministic scanner output into the same report.

| Item | Status | Notes |
|------|--------|-------|
| Plugin interface | [ ] | Detect-if-installed; never hard-fail LLM path |
| Secret scanning adapter (e.g. gitleaks) | [ ] | Optional extra / download-with-consent |
| SAST adapter (e.g. Semgrep) | [ ] | OWASP-oriented rulesets where licensed |
| Dependency / CVE adapter (e.g. OSV) | [ ] | Real CVE enumeration |
| Optional `repolens[scanners]` / `plugins install` | [ ] | Not in slim default wheel |
| Section in report: “Automated scanners” | [ ] | |
| Docs: enabling plugins | [ ] | |

**Phase 3 exit criteria:** Plugins optional; CLI works without them; when enabled, findings merge cleanly.

---

## Phase 4 — CI & ecosystem

**Goal:** Run RepoLens in pipelines and grow adoption.

| Item | Status | Notes |
|------|--------|-------|
| GitHub Action (official workflow) | [ ] | |
| Bitbucket Pipe or documented script | [ ] | |
| Pre-built binaries / package publish | [ ] | PyPI and/or npm |
| Example configs for monorepos | [ ] | |
| Confidence / history log helpers | [ ] | Optional `docs/review-confidence-log.md` |
| Local ML learning (opt-in, on-disk only) | [ ] | `.repolens/` index + memory; informed consent; no phone-home |
| Privacy notice + `local_learning` config | [ ] | See design/ai-keys-scanners-and-local-learning.md |

**Phase 4 exit criteria:** Documented CI example; published install path; local-learning design implemented or explicitly deferred with FAQ accuracy.

---

## Non-goals (for now)

- Web dashboard / SaaS UI  
- Auto-commit or auto-push  
- Replacing Snyk/CodeQL/Dependabot as the sole security program  
- Claiming zero false positives from LLM-only analysis  
- Shipping a shared/cloud RepoLens API key  
- Training a global model on user repositories  
- Silent local learning without consent  
- Claiming CVE-complete coverage from the LLM playbook alone  

---

## Decision log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-08-04 | Product name **RepoLens**; security mode **`sentinel`** | Broad audit identity + clear security-only command |
| 2026-08-04 | Open source, MIT, GitHub community files from day one | Anyone can adopt playbooks and contribute |
| 2026-08-04 | CLI-first; no UI in early phases | Focus on portable reviews |
| 2026-08-04 | Root = `README` + `LICENSE` only for docs; rest under `docs/` | Clean root; GitHub still finds community files in `/docs` |
| 2026-08-04 | `phases.md` kebab-case; keep `CONTRIBUTING.md` etc. uppercase | Only GitHub/Keep-a-Changelog conventional names use CAPS |
| 2026-08-04 | CLI language **Python 3.11+** (`typer`/`rich`/`pydantic`/`httpx`) | Scanner ecosystem + HF/git scripting; `pipx`/`uv` distribution |
| 2026-08-04 | Target review: language-agnostic with first-class JS/TS, Python, Go, JVM, C#, Ruby, PHP, Rust, Swift | Match real multi-stack adoption; IaC/config first-class for security |
| 2026-08-04 | Phase 0 complete | Design + FAQ + language locked; ready for Phase 1 scaffold |
| 2026-08-04 | Phase 1 alpha scaffold | Local CLI `0.1.0a1`: review/sentinel/init, schema, pytest CI |
| 2026-08-04 | Phase 2 MVP | `--git-url` + `--github`; cwd reports; env/`gh` auth |
| 2026-08-04 | ADR-01 + `_diagram_legend.md` | Document how analysis works with Mermaid architecture views |
| 2026-08-04 | BYOK + local Ollama; no embedded AI key | Self-sufficient only with local model; cloud is opt-in network |
| 2026-08-04 | Scanners optional extras, not slim default | Detect-if-installed; CVE via OSV-class tools; OWASP via LLM+Semgrep layers |
| 2026-08-04 | Local learning opt-in, on-disk, informed | No RepoLens training cloud; disclose cloud LLM still sends excerpts |

---

## How to update this file

1. Check boxes when a PR merges.  
2. Add a one-line note if scope changed.  
3. Mirror user-visible changes in `CHANGELOG.md`.  
4. Open an issue for phase-exit blockers instead of silently slipping criteria.
