# RepoLens — Implementation phases

Track what is planned, in progress, and done. Update checkboxes as work lands.  
For release notes aimed at users, also update [CHANGELOG.md](./CHANGELOG.md).

**Product name:** RepoLens  
**Security-only mode:** `repolens sentinel`  
**Full review mode:** `repolens review` (P1 → P2 → P3)

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
| Repository created under `/Users/vivek/Development/RepoLens` | [x] | |
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
| Choose implementation language (Python vs TypeScript) | [ ] | Decision before Phase 1 coding |
| Design spec for CLI UX & report schema | [ ] | `docs/design/` when approved |

**Phase 0 exit criteria:** Docs + playbooks + community files on `main`; language/design decided.

---

## Phase 1 — Core CLI (local only)

**Goal:** `repolens review` and `repolens sentinel` work on a local `--path`.

| Item | Status | Notes |
|------|--------|-------|
| Package scaffold + `repolens` entrypoint | [ ] | |
| Config file (`~/.config/repolens/` or project `.repolens.toml`) | [ ] | API keys, report dir, model |
| Load playbooks from `playbooks/` | [ ] | |
| `repolens sentinel` — security-only (P1) | [ ] | |
| `repolens review` — P1 → P2 → P3 on local tree/diff | [ ] | |
| Finding schema: severity, impact, fix, codeExample (required Critical/High) | [ ] | |
| Confidence % in summary | [ ] | |
| Write `reports/gate_review_report_YYYY-MM-DD.md` | [ ] | |
| `repolens export` (Markdown path; PDF if pandoc present) | [ ] | |
| Unit/integration tests (TDD) for report writer & CLI args | [ ] | |
| User docs: install + first review | [ ] | |

**Phase 1 exit criteria:** Local full + sentinel reviews produce Markdown reports with mandatory Critical/High code examples; tests green in CI.

---

## Phase 2 — Multi-source ingest

**Goal:** Review repos that are not already on disk.

| Item | Status | Notes |
|------|--------|-------|
| Generic `--git-url` (+ `--ref`) shallow clone to temp | [ ] | Cleanup after run |
| `--github owner/repo` | [ ] | Token via env / `gh` |
| `--bitbucket workspace/repo` | [ ] | App password / token |
| `--hf` Hugging Face Hub git repos | [ ] | `HF_TOKEN` when private |
| Size limits / ignore globs / P1 file prioritization | [ ] | Align with P1→P3 ordering |
| Docs: auth for each host | [ ] | |

**Phase 2 exit criteria:** Same commands work for local and at least GitHub + generic git URL; secrets never logged.

---

## Phase 3 — Durability plugins (optional analyzers)

**Goal:** Merge deterministic scanner output into the same report.

| Item | Status | Notes |
|------|--------|-------|
| Plugin interface | [ ] | |
| Secret scanning adapter (e.g. gitleaks) | [ ] | |
| SAST adapter (e.g. Semgrep) | [ ] | |
| Dependency / CVE adapter (e.g. OSV) | [ ] | |
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

**Phase 4 exit criteria:** Documented CI example; published install path for outsiders.

---

## Non-goals (for now)

- Web dashboard / SaaS UI  
- Auto-commit or auto-push  
- Replacing Snyk/CodeQL/Dependabot as the sole security program  
- Claiming zero false positives from LLM-only analysis  

---

## Decision log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-08-04 | Product name **RepoLens**; security mode **`sentinel`** | Broad audit identity + clear security-only command |
| 2026-08-04 | Open source, MIT, GitHub community files from day one | Anyone can adopt playbooks and contribute |
| 2026-08-04 | CLI-first; no UI in early phases | Focus on portable reviews |
| 2026-08-04 | Root = `README` + `LICENSE` only for docs; rest under `docs/` | Clean root; GitHub still finds community files in `/docs` |
| 2026-08-04 | `phases.md` kebab-case; keep `CONTRIBUTING.md` etc. uppercase | Only GitHub/Keep-a-Changelog conventional names use CAPS |

---

## How to update this file

1. Check boxes when a PR merges.  
2. Add a one-line note if scope changed.  
3. Mirror user-visible changes in `CHANGELOG.md`.  
4. Open an issue for phase-exit blockers instead of silently slipping criteria.
