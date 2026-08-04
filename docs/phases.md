# RepoLens — Implementation phases

Track what is planned, in progress, and done. Update checkboxes as work lands.  
For release notes aimed at users, also update [CHANGELOG.md](./CHANGELOG.md).

**Product name:** RepoLens  
**Security-only mode:** `repolens sentinel`  
**Full review mode:** `repolens review` (P1 → P2 → P3)  
**Current phase:** Phase 4 complete; Phase 5 adaptive cache in progress; **deep coverage (B+C+D)** shipping (heuristics + chunked passes + rules registry + graceful LLM spine); Phase A (cloud as quality multiplier) docs-only  

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
| `--bitbucket workspace/repo` | [x] | `BITBUCKET_TOKEN` / app password |
| `--hf` Hugging Face Hub git repos | [x] | `HF_TOKEN`; models/datasets/spaces |
| Size limits / ignore globs / P1 file prioritization | [x] | Reuses Phase 1 inventory |
| Docs: auth for each host | [x] | `docs/remote-sources.md` (GitHub + git-url) |

**Phase 2 exit criteria:** Same commands work for local and at least GitHub + generic git URL; secrets never logged. → **Met (2026-08-04)** including Bitbucket + Hugging Face.

---

## Phase 3 — Durability plugins (optional analyzers)

**Goal:** Merge deterministic scanner output into the same report.

| Item | Status | Notes |
|------|--------|-------|
| Plugin interface | [x] | Detect PATH + `~/.cache/repolens/tools/`; LLM path never hard-fails |
| Secret scanning adapter (e.g. gitleaks) | [x] | `scanners/gitleaks.py` |
| SAST adapter (e.g. Semgrep) | [x] | `scanners/semgrep.py` (`--config auto`) |
| Dependency / CVE adapter (e.g. OSV) | [x] | `scanners/osv.py` |
| Optional `repolens[scanners]` / `plugins install` | [x] | Consent download; `--yes` for CI; Semgrep via pip extra |
| Section in report: “Automated scanners” | [x] | Markdown + `scannerRuns` JSON |
| Docs: enabling plugins | [x] | `docs/scanners.md` · design note |

**Phase 3 exit criteria:** Plugins optional; CLI works without them; when enabled, findings merge cleanly. → **Met (2026-08-04)**

---

## Phase 4 — CI & ecosystem

**Goal:** Run RepoLens in pipelines and grow adoption.

| Item | Status | Notes |
|------|--------|-------|
| GitHub Action (official workflow) | [x] | Root `action.yml` + `repolens-example.yml` |
| Bitbucket Pipe or documented script | [x] | Script in `docs/ci.md` (no marketplace Pipe) |
| Pre-built binaries / package publish | [x] | Trusted Publishing workflow + `docs/publishing.md` |
| Example configs for monorepos | [x] | `examples/monorepo/` |
| Confidence / history log helpers | [x] | `docs/review-confidence-log.md` |
| Local ML learning (opt-in, on-disk only) | [x] | FTS index + memory; `[local-ml]` optional |
| Privacy notice + `local_learning` config | [x] | Consent gate + `docs/local-learning.md` |

**Phase 4 exit criteria:** Documented CI example; published install path; local-learning design implemented or explicitly deferred with FAQ accuracy. → **Met (2026-08-04)** (PyPI upload needs one-time Trusted Publisher setup)

---

## Phase 5 — Adaptive fingerprint cache & recommendations (design)

**Goal:** Per-project progressive review cache + configurable timeout/ETA recommendations so users do not need to discover knobs the hard way.

| Item | Status | Notes |
|------|--------|-------|
| Design: dual-store fingerprint + opt-in content | [x] | [phase-5-adaptive-cache-and-recommendations.md](./design/phase-5-adaptive-cache-and-recommendations.md) |
| Unified SQLite (`repolens.sqlite`) + FTS5 | [x] | `ProjectStore` + migrate `index.sqlite` → `.bak`; learning uses same DB |
| Fingerprint sync + timeout helpers | [x] | `adaptive.py` + `[adaptive]` config (pipeline wire-up next) |
| Adaptive LLM pack (`auto` / `full` / `changed`) | [x] | Wired in `run_review`; CLI `--full` |
| Per-project timeout recommendation + overrides | [x] | Applied when `[model].timeout_seconds` unset; else stored in meta |
| Incremental FTS when content learning consented | [x] | Upsert/delete on review when consent present |
| `repolens adaptive status` | [x] | Fingerprints + recommended timeout + pending diff |
| User docs (FAQ / setup / try-on) for adaptive UX | [~] | Design done; expand user guides next |

**Phase 5 exit criteria:** Warm re-review on a large repo uses a smaller LLM pack in `auto` mode; recommended timeout is project-specific and overridable; content learning remains opt-in.

---

## Deep coverage review (B+C+D; Phase A later)

**Goal:** Large-repo local reviews beat thin single-shot reports via heuristics, chunked P1→P3 passes, and a checklist coverage matrix. Rules load by **id** from a registry (not hard-coded author-machine Markdown paths). Cloud Anthropic/OpenAI later use the **same `--deep` pipeline**.

| Item | Status | Notes |
|------|--------|-------|
| Graceful 4-layer LLM spine (ask → coerce → micro-repair → degrade; exit 0) | [x] | Never abort without a report |
| Rules registry + coverage matrix | [x] | Project → user → packaged defaults by id |
| Heuristics pre-pass (D) | [x] | Mega-files, siblings, gitignore/secrets hygiene, … |
| Deep planner + merge + CLI `--deep` / `--no-deep` | [x] | Default on; `--no-deep` = single-shot |
| Guided script + user docs | [x] | Deep Y/n + FAQ / setup / CHANGELOG |
| Phase A: Anthropic/OpenAI as provider multiplier | [ ] | Docs tip only — same `--deep` pipeline |

**Exit criteria:** PatternSorcerer-class `review --full-audit --deep` with a local model surfaces structural themes without requiring Claude; `--no-deep` preserved.

---

## Phase 6 — Enterprise CI/CD & report delivery (design)

**Goal:** Production-minded corporate use: CI agents (Jenkins, CircleCI, GitLab, …), artifact export, email/chat/dashboard handoff — without building a RepoLens SaaS UI.

| Item | Status | Notes |
|------|--------|-------|
| Design sketch | [x] | [phase-6-enterprise-ci-and-report-delivery.md](./design/phase-6-enterprise-ci-and-report-delivery.md) |
| Expand [ci.md](./ci.md) (Jenkins / CircleCI / GitLab) | [ ] | |
| Artifact → email / webhook recipes | [ ] | Customer SMTP / forge plugins |
| Adaptive cache guidance for ephemeral CI | [ ] | Off by default or restore via CI cache |
| Dashboard ingest (JSON) recipe | [ ] | External dashboard; no hosted RepoLens UI |
| FAQ “Corporate CI/CD” | [ ] | |

**Phase 6 exit criteria:** A security/platform engineer can wire RepoLens into Jenkins or CircleCI, archive reports, optionally email/notify, and know when to disable adaptive learning on CI.

---

## Non-goals (for now)

- Web dashboard / SaaS UI (Phase 6 may document **external** dashboard ingest only)  
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
| 2026-08-04 | Phase 2 complete | `--bitbucket` + `--hf`; all planned remotes |
| 2026-08-04 | Phase 3 complete | Optional scanners + `plugins install`; report merge |
| 2026-08-04 | Phase 4 complete | Action, publish workflow, local learning, CI docs |
| 2026-08-04 | ADR-01 + `_diagram_legend.md` | Document how analysis works with Mermaid architecture views |
| 2026-08-04 | BYOK + local Ollama; no embedded AI key | Self-sufficient only with local model; cloud is opt-in network |
| 2026-08-04 | Scanners optional extras, not slim default | Detect-if-installed; CVE via OSV-class tools; OWASP via LLM+Semgrep layers |
| 2026-08-04 | Local learning opt-in, on-disk, informed | No RepoLens training cloud; disclose cloud LLM still sends excerpts |
| 2026-08-04 | Phase 5 design: fingerprint always-on + content opt-in | Progressive cache; per-project timeout; unified SQLite+FTS5 |
| 2026-08-04 | Phase 5: local-first; network repo paths later | RW permissions / local cache redirect when network lands |
| 2026-08-04 | Phase 6 design: enterprise CI + report delivery | Jenkins/CircleCI/email/dashboard via artifacts — not RepoLens SaaS |
| 2026-08-04 | Deep coverage B+C+D first; A (cloud) later | Same `--deep` pipeline for Anthropic/OpenAI; rules by registry id |

---

## How to update this file

1. Check boxes when a PR merges.  
2. Add a one-line note if scope changed.  
3. Mirror user-visible changes in `CHANGELOG.md`.  
4. Open an issue for phase-exit blockers instead of silently slipping criteria.
