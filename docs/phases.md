# RepoLens — Implementation phases

Track what is planned, in progress, and done. Update checkboxes as work lands.  
For release notes aimed at users, also update [CHANGELOG.md](./CHANGELOG.md).

**Product name:** RepoLens  
**Security-only mode:** `repolens sentinel`  
**Full review mode:** `repolens review` (P1 → P2 → P3)  
**Current phase:** Phases **2–5.2 complete**; **next** Phase 6 explain/diagrams → Phase 7 enterprise CI → Phase 8 provider aliases → Phase 9 native SDKs  

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
| Write `reports/gate_review_report_{mode}_YYYY-MM-DD_HHMM.md` | [x] | + JSON; mode + time avoid overwrite |
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
| Adaptive LLM pack (`auto` / `full` / `changed`) | [x] | Wired in `run_review`; CLI `--full` / `--changed` |
| Per-project timeout recommendation + overrides | [x] | Applied when `[model].timeout_seconds` unset; else stored in meta |
| Incremental FTS when content learning consented | [x] | Upsert/delete on review when consent present |
| `repolens adaptive status` | [x] | Fingerprints + recommended timeout + pending diff |
| User docs (FAQ / setup / try-on) for adaptive UX | [x] | FAQ adaptive table; setup + try-on warm-run tips |

**Phase 5 exit criteria:** Warm re-review on a large repo uses a smaller LLM pack in `auto` mode; recommended timeout is project-specific and overridable; content learning remains opt-in. → **Met (2026-08-05)**

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
| Phase A: Anthropic/OpenAI as provider multiplier | [x] | Docs tip — same `--deep` pipeline + streamed wait UX |

**Exit criteria:** PatternSorcerer-class `review --full-audit --deep` with a local model surfaces structural themes without requiring Claude; `--no-deep` preserved. → **Met (2026-08-05)** (Phase A = docs + shared pipeline)

---

## Phase 5.1 — Deep coverage hardening (design)

**Goal:** Honest coverage/N/A, multi-metric confidence (including **security audit confidence**), quieter heuristics, band sanity, per-pass progress UX.

| Item | Status | Notes |
|------|--------|-------|
| Design approved | [x] | [phase-5.1-deep-hardening.md](./design/phase-5.1-deep-hardening.md) · [spec](./superpowers/specs/2026-08-04-phase-5.1-deep-hardening-design.md) |
| Lazy N/A rejection + coverage honesty | [x] | `is_lazy_na_reason` → missed |
| Gate + security (+ arch/rel) audit confidence + glossary | [x] | `metrics.py` + report Metrics section |
| Mega-file ignore globs (docs/xcuserdata/pbxproj) | [x] | Configurable via `[deep]` |
| Priority/band sanity | [x] | `bands.coerce_issue_bands` |
| Per-pass progress timers | [x] | `waiting` inside deep pass loop |
| Streamed LLM wait + report duration / mode stamps | [x] | Ollama + BYOK SSE; `durationSeconds`; `{mode}_HHMM` filenames |
| Sentinel metrics omit unscored bands | [x] | Arch/rel `None`, not 0%; gate from ran passes only |

**Phase 5.1 exit criteria:** PatternSorcerer deep report explains metrics; confidence not stuck at raw LLM 95% with weak coverage; security audit confidence visible; timers reset per pass. → **Met (2026-08-05)**

---

## Phase 5.2 — Theme coverage & report breakdown (design)

**Goal:** First-class **Core + Extended** themes with honest coverage ids and a **Theme breakdown** section (Core always on deep review; Extended on `--full-audit` / N/A when irrelevant) — so product claims match the report shape.

| Item | Status | Notes |
|------|--------|-------|
| Design approved (Core + Extended) | [x] | [phase-5.2-theme-coverage-and-report-breakdown.md](./design/phase-5.2-theme-coverage-and-report-breakdown.md) |
| Core theme ids (18) + deprecations/aliases | [x] | Replaced coarse `arch.code_quality` / `arch.structure` |
| Extended theme ids (~19) | [x] | full-audit in Theme breakdown; N/A when out of scope |
| Heuristic → theme mapping | [x] | mega_file, siblings, gitignore_secrets, … |
| Report/JSON Theme breakdown (Core / Extended) | [x] | covered / N/A / missed + finding counts |
| Optional light heuristics (complexity / TLS hints) | [ ] | Deferred (deterministic only; no heavy clone graph) |
| FAQ + product honesty | [x] | FAQ Core vs Extended; product page can cite Theme breakdown |

**Phase 5.2 exit criteria:** Deep full-audit report lists Core + Extended themes with coverage and finding counts; non-full-audit deep shows Core only; sentinel shows Core P1 only; heuristics map into themes; no double-count of deprecated parents. → **Met (2026-08-05)** (optional light heuristics deferred)

---

## Phase 6 — Issue explain + foolproof diagrams (design)

**Goal:** UUID per issue (`stableId` + `runId`); explain toggle; deep-dive command with solutions + Mermaid/textual diagrams that never abort on render failure.

| Item | Status | Notes |
|------|--------|-------|
| Design approved | [x] | [phase-6-issue-explain-diagrams.md](./design/phase-6-issue-explain-diagrams.md) · [spec](./superpowers/specs/2026-08-04-phase-6-issue-explain-diagrams-design.md) |
| Issue IDs on FindingReport | [ ] | |
| `[explain]` config + `repolens explain` + `review --explain` | [ ] | |
| Diagram spine (validate → repair → fallback → optional image) | [ ] | Exit 0 |

**Phase 6 exit criteria:** User can deep-dive any finding by UUID and always get an explain file; invalid Mermaid yields textual fallback.

---

## Phase 7 — Enterprise CI/CD & report delivery (design)

**Goal:** Production-minded corporate use: CI agents (Jenkins, CircleCI, GitLab, …), artifact export, email/chat/dashboard handoff — without building a RepoLens SaaS UI.  
*(Formerly Phase 6 — renumbered 2026-08-04.)*

| Item | Status | Notes |
|------|--------|-------|
| Design sketch | [x] | [phase-7-enterprise-ci-and-report-delivery.md](./design/phase-7-enterprise-ci-and-report-delivery.md) |
| Expand [ci.md](./ci.md) (Jenkins / CircleCI / GitLab) | [ ] | |
| Artifact → email / webhook recipes | [ ] | Customer SMTP / forge plugins |
| Adaptive cache guidance for ephemeral CI | [ ] | Off by default or restore via CI cache |
| Dashboard ingest (JSON) recipe | [ ] | External dashboard; no hosted RepoLens UI |
| FAQ “Corporate CI/CD” | [ ] | |

**Phase 7 exit criteria:** A security/platform engineer can wire RepoLens into Jenkins or CircleCI, archive reports, optionally email/notify, and know when to disable adaptive learning on CI.

---

## Phase 8 — Provider aliases & setup recipes (design)

**Goal:** Named `repolens init` aliases + docs/recipes for common hosts (Azure OpenAI, Mistral, Groq, OpenRouter, …) on the existing OpenAI-compatible transport. **Options 1 + 2** from the provider expansion discussion.  
**Not in this phase:** Native Gemini/Bedrock SDKs → Phase 9. Enterprise CI → Phase 7.

| Item | Status | Notes |
|------|--------|-------|
| Design sketch | [x] | [phase-8-provider-aliases-and-recipes.md](./design/phase-8-provider-aliases-and-recipes.md) · [spec](./superpowers/specs/2026-08-05-phase-8-provider-aliases-design.md) |
| P0 aliases: Azure, Mistral, Groq, OpenRouter | [ ] | Map to OpenAI-compatible + stream |
| Setup/FAQ recipes (P0–P2) | [ ] | LM Studio / vLLM as `openai_compatible` |
| Gemini: recipe or “see Phase 9” | [ ] | No half-native adapter in Phase 8 |

**Phase 8 exit criteria:** Users can `init --provider groq|mistral|azure|openrouter` (and follow recipes for self-hosted OpenAI-compatible hosts) without hand-editing obscure `base_url`s.

---

## Phase 9 — Native provider SDKs (design)

**Goal:** First-party adapters where the wire protocol is **not** OpenAI chat completions (**Option 3**): Gemini / Vertex, Bedrock, and similar — only when Phase 8 aliases are insufficient.

| Item | Status | Notes |
|------|--------|-------|
| Design sketch | [x] | [phase-9-native-provider-sdks.md](./design/phase-9-native-provider-sdks.md) · [spec](./superpowers/specs/2026-08-05-phase-9-native-provider-sdks-design.md) |
| Native Gemini and/or Vertex | [ ] | Stream → `on_delta` |
| Native Bedrock (if demanded) | [ ] | Prefer Converse + thin httpx |
| Keep Phase 8 aliases on OpenAI-compatible path | [ ] | Do not rewrite without cause |

**Phase 9 exit criteria:** At least one native provider ships with init + streaming wait UX + tests; FAQ clearly marks alias vs native.

---

## Non-goals (for now)

- Web dashboard / SaaS UI (Phase 7 may document **external** dashboard ingest only)  
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
| 2026-08-04 | Enterprise CI design as Phase 6 (later renumbered to 7) | Jenkins/CircleCI/email/dashboard via artifacts — not RepoLens SaaS |
| 2026-08-04 | Deep coverage B+C+D first; A (cloud) later | Same `--deep` pipeline for Anthropic/OpenAI; rules by registry id |
| 2026-08-04 | Phase 5.1 hardening + Phase 6 explain/diagrams; enterprise → Phase 7 | Honest metrics incl. security audit confidence; foolproof Mermaid |
| 2026-08-04 | Confidence is multi-metric | Gate confidence ≠ security audit confidence ≠ architecture scores |
| 2026-08-05 | Provider expansion = Phase 8 + 9, not Phase 7 | Phase 7 = enterprise CI only; Phase 8 = aliases + recipes (opts 1–2); Phase 9 = native SDKs (opt 3) |
| 2026-08-05 | Phases 5 + 5.1 + deep coverage (incl. Phase A docs) complete | Adaptive user docs finished; metrics/stream/sentinel polish landed |
| 2026-08-05 | Phase 5.2 theme coverage & report breakdown (design) | Product themes need first-class coverage ids + Theme breakdown; not only P1/P2/P3 prose |
| 2026-08-05 | Phase 5.2 packing = Core (18) + Extended (~19) | Core every deep review; Extended on full-audit / N/A when irrelevant |
| 2026-08-05 | Phase 5.2 implemented | Theme breakdown in reports; coverage v2 packs; heuristic→theme map; FAQ |

---

## How to update this file

1. Check boxes when a PR merges.  
2. Add a one-line note if scope changed.  
3. Mirror user-visible changes in `CHANGELOG.md`.  
4. Open an issue for phase-exit blockers instead of silently slipping criteria.
