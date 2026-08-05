# Phase 5.2 — Theme coverage & report breakdown

**Status:** Implemented (2026-08-05) — Core + Extended Theme breakdown; optional light heuristics deferred  
**Depends on:** Phase 5.1 (deep coverage + metrics)  
**Related:** [coverage.json](../../src/repolens/rules/defaults/coverage.json), deep coverage design, product claims for RepoLens

## Problem

Users (and the Products page) expect RepoLens to help find named themes and show them in the report. Today playbooks and coarse coverage ids cover much of this *in prose*, but the Markdown/JSON report only groups by **P1 / P2 / P3** plus covered/N/A/missed — not a scannable theme table.

## Goal

Make themes **first-class** in two packs:

1. **Core** — always in deep `review` / applicable `sentinel` P1 rows  
2. **Extended** — included on `--full-audit`, or when the pack is clearly in scope; otherwise honest **N/A** with a short reason  

Each theme has a stable coverage id, deep passes are accountable for Core (and Extended when in play), and the report includes a **Theme breakdown** section.

## Non-goals

- Claiming static-analysis completeness (no full unused-code graph or cyclomatic tooling in core)
- Replacing Semgrep/OSV/gitleaks/CodeQL
- Reordering Phase 6 explain/diagrams or Phase 7+ CI/provider work
- Auto-scoring “% clean” per theme
- One theme per OWASP bullet (keep the table scannable: ~20–25 ids total)

## Packing: Core + Extended

### Core (ship first — every deep review)

| Id | Band | Theme | Notes |
|----|------|--------|-------|
| `arch.structure_size` | P3 | Structure & size | Mega-files, modularity, blast radius |
| `arch.readability_complexity` | P3 | Readability & complexity | Large functions, nesting, naming clarity |
| `arch.duplication` | P3 | Duplication | Sibling / copy-paste / overlapping modules |
| `arch.dead_code` | P3 | Dead code & leftovers | Unused files, commented-out code, TODOs/FIXME |
| `arch.consistency_style` | P3 | Consistency & style | Naming and pattern drift |
| `sec.repo_hygiene_secrets` | P1 | Repo hygiene, secrets & credentials | Absorbs/aliases today’s `sec.secrets` + hygiene heuristics |
| `sec.injection` | P1 | Injection & unsafe code | SQL/command and related unsafe sinks |
| `sec.xss_csrf` | P1 | XSS / CSRF / web surface | Keep existing id |
| `sec.authn_authz` | P1 | Auth & access control | Keep existing id |
| `sec.data_exposure` | P1 | Data exposure | Logging PII, error leakage, client-side secrets |
| `sec.deps_supply_chain` | P1 | Dependencies & supply chain | Rename of `sec.deps_config` (deprecate old id) |
| `sec.transport_tls` | P1 | Transport & TLS | Insecure HTTP, TLS/cookie/redirect misuse |
| `sec.crypto_deser` | P1 | Crypto & deserialization | Keep existing id |
| `sec.input_validation` | P1 | Input validation | Keep existing id |
| `rel.edge_cases` | P2 | Edge cases & null handling | Keep existing id |
| `rel.concurrency` | P2 | Concurrency & races | Keep existing id |
| `rel.error_recovery` | P2 | Error recovery & resilience | Keep existing id |
| `rel.performance` | P2 | Performance hotspots | Keep existing id |

**Core count:** 18 themes.

### Extended (full-audit or N/A when irrelevant)

| Id | Band | Theme | `full_audit_only` | Notes |
|----|------|--------|-------------------|-------|
| `arch.database` | P3 | Database & data integrity | yes | Keep / promote existing |
| `arch.api` | P3 | API design & consistency | no* | In Core path when API surface present; else N/A |
| `arch.frontend` | P3 | Frontend patterns | yes | UX/state patterns |
| `arch.a11y` | P3 | Accessibility (a11y) | yes | Split from frontend for clarity |
| `arch.testing` | P3 | Testing strategy | no* | Promote existing; N/A only if no testable app |
| `arch.observability` | P3 | Observability | yes | Logging, metrics, tracing, alerting |
| `arch.ci_durability` | P3 | CI/CD & release durability | no* | Tests/CI/scanners/staging/backups/runbooks |
| `arch.iac_cloud` | P1/P3 | IaC / cloud misconfig | yes | Docker, K8s, CI YAML, cloud templates |
| `arch.i18n` | P3 | Internationalisation (i18n) | yes | Hard-coded copy, mega locale files |
| `arch.pwa` | P3 | PWA / offline / service worker | yes | Keep existing |
| `arch.licensing` | P3 | Licensing & compliance | yes | Licence files, third-party notices |
| `arch.scalability` | P3 | Scalability & capacity | yes | Aligns with architecture score dimension |
| `sec.config_env` | P1 | Config & environment safety | yes | Debug-on, CORS, feature flags, env split |
| `sec.privacy_pii` | P1 | Privacy & PII handling | yes | Retention, consent, redaction (broader than data exposure) |
| `sec.upload_path` | P1 | File upload & path traversal | yes | Common OWASP gap |
| `sec.session_cookies` | P1 | Session & cookie security | yes | Optional split from auth when sharp findings |
| `sec.rate_abuse` | P1 | Rate limiting & abuse | yes | Brute-force / DoS surface |
| `sec.build_release` | P1 | Build & release integrity | yes | Lockfiles, Action pin-to-SHA, signed releases |
| `arch.documentation` | P3 | Documentation & onboarding | yes | DevEx / README / architecture docs |

\* `full_audit_only: false` but expected **N/A** on tiny/library packs with no API/UI/CI — same honesty rules as 5.1 lazy-N/A rejection.

**Extended count:** ~19 themes (report shows them under an “Extended” subheading; Core stays first).

### Deprecated / replaced coarse ids

Prefer **replace** (no double-count in confidence math):

| Old id | Disposition |
|--------|-------------|
| `arch.structure` | Replaced by `arch.structure_size` (+ related Core) |
| `arch.code_quality` | Replaced by readability / duplication / dead_code / consistency |
| `arch.security_surface` | Folded into Core `sec.*` themes |
| `arch.dependencies` | Folded into `sec.deps_supply_chain` (arch hygiene notes → same theme) |
| `arch.performance` | Folded into `rel.performance` (+ scalability Extended) |
| `arch.reliability` | Folded into Core `rel.*` |
| `arch.durability` | Replaced by `arch.ci_durability` |
| `arch.devex` | Split into documentation + consistency/style |
| `arch.scores` / `arch.blast_radius` | Keep as non-theme mechanics if still needed; not Theme-breakdown rows |
| `sec.secrets` | Alias → `sec.repo_hygiene_secrets` |
| `sec.deps_config` | Alias → `sec.deps_supply_chain` |
| `sec.practice_review` | Drop as coverage id; practices live inside themes |

## Heuristic → theme mapping

| Heuristic category | Theme id |
|--------------------|----------|
| `heuristic.mega_file` | `arch.structure_size` |
| `heuristic.sibling_duplication` | `arch.duplication` |
| `heuristic.gitignore_secrets` | `sec.repo_hygiene_secrets` |
| `heuristic.scripts_hygiene` / `todo_density` | `arch.dead_code` |
| `heuristic.ci_gaps` | `arch.ci_durability` (and note supply-chain scanner gaps under `sec.deps_supply_chain` when relevant) |

## Report: Theme breakdown

After Metrics (or after Coverage), render:

```markdown
## Theme breakdown

### Core

| Theme | Coverage | Findings | Notes |
|-------|----------|----------|-------|
| Structure & size | covered / N/A / missed | N | … |
| … | … | … | … |

### Extended

| Theme | Coverage | Findings | Notes |
|-------|----------|----------|-------|
| Database & data integrity | N/A | 0 | no persistence layer |
| … | … | … | … |
```

Rules:

- **Core** rows always for deep `review`; **sentinel** shows Core **P1** only (mirror 5.1 unscored-band omission).
- **Extended** rows on `--full-audit`; on non-full-audit deep review, either omit Extended or show only themes that were in the pass plan (document one behaviour — recommend: omit Extended unless full-audit).
- **Coverage** from `evaluate_coverage` for that theme id.
- **Findings** = issues whose `category` matches theme id, heuristic map, or optional `theme` field.
- JSON: `themes: [{ id, pack: "core"|"extended", title, status, findingCount, issueRefs[] }]`.

## Optional light heuristics (only if cheap)

- Large function line spans → `arch.readability_complexity`
- `http://` in non-test source / weak TLS config hints → `sec.transport_tls`
- Fold TODO density into `arch.dead_code`

Defer heavy clone-detection / full unused-export analysis.

## Product / FAQ honesty

Once shipped:

> Deep reviews track **Core** themes in every run and **Extended** themes on full audit (or N/A when irrelevant). Heuristics seed some themes; LLM + optional scanners fill the rest. Not a substitute for dedicated SCA/SAST.

## Exit criteria

1. Coverage matrix lists Core + Extended ids; tests sync matrix ↔ rules; deprecated ids aliased or removed without double penalties.
2. Deep `review --full-audit` report includes Theme breakdown with **Core** and **Extended** subsections.
3. Deep `review` without full-audit includes **Core** only; `sentinel` includes Core P1 only.
4. Mega-file, sibling duplication, and gitignore/secrets heuristics contribute to mapped theme finding counts.
5. FAQ documents Core vs Extended, bands, and covered / N/A / missed.
6. Confidence math does not double-penalize deprecated parent + child themes.

## Suggested implementation order

1. Theme registry (`pack: core|extended`) + coverage.json + deprecation aliases + tests  
2. Heuristic → theme mapping + category normalisation  
3. Report/JSON Theme breakdown (Core / Extended)  
4. Playbook/rule text anchors  
5. Optional light heuristics  
6. FAQ + CHANGELOG + product bullet once green  

## Decisions (locked)

1. **Replace** coarse `arch.code_quality` / `arch.structure` with Core themes (no nest-and-double-count).  
2. **`sec.deps_config` → `sec.deps_supply_chain`** with temporary alias acceptance in coverage matching.  
3. **Sentinel:** Core P1 themes only in breakdown.  
4. **Extended** primarily on `--full-audit`; honest N/A when out of scope.
