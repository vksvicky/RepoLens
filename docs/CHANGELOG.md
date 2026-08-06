# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once the first release is tagged.

## [Unreleased]

### Added (Phase 6 issue explain + diagrams)

- Hybrid issue IDs: `stableId` (UUID v5) + `runId` (UUID v4) on every finding; shown in Markdown reports
- `[explain]` config + `repolens explain <uuid>` + `review --explain uuid[,…]`
- Foolproof diagram spine: Mermaid validate → one repair → textual fallback; optional `mmdc` image never blocks exit 0
- `.repolens/last_report.json` pointer (and JSON sidecar when `--format md`) for explain lookup

### Added (Phase 6.x design — not implemented yet)

- Roadmap for scanner depth / CI triage / anchored SARIF / suppressions before Phase 7 ([design](./design/phase-6.x-scanner-depth-ci-gates-and-credibility.md))
- Implementation plan for enterprise CI triage routing ([plan](./superpowers/plans/2026-08-06-enterprise-ci-triage-routing.md))
- Blog draft: enterprise scale vs full-LLM PR checks ([blog](./blog-ideas/enterprise-scale-llm-review-ci.md))
- End-user [rules.md](./rules.md) + AppSec comparison note

### Added

- Standard **AI / LLM disclaimer** on every Markdown gate report; FAQ + README pointers (no liability for reliance on AI/tool-assisted output)

### Added (Phase 5.2 theme coverage & report breakdown)

- **Core + Extended** theme registry in `coverage.json` (`pack: core|extended|meta`)
- Report **Theme breakdown** (Markdown + JSON `themes[]`): Core on every deep review; Extended on `--full-audit`; sentinel = Core P1 only
- Heuristic → theme mapping (mega-file, siblings, gitignore/secrets, scripts/TODO, CI gaps)
- Coverage id aliases (`sec.secrets` → `sec.repo_hygiene_secrets`, `sec.deps_config` → `sec.deps_supply_chain`)
- FAQ: Core vs Extended themes; design doc updated

### Added (Phase 5.1 deep hardening)

- **Gate confidence** recalibrated from coverage (lazy N/A → missed); separate **security / architecture / reliability audit confidence**
- Report **Metrics** glossary (confidence ≠ “% secure”); CLI summary shows security audit %
- Mega-file heuristic skips docs / `xcuserdata` / `pbxproj` by default
- Priority band coercion (heuristics / non-`sec.*` off P1)
- Deep progress wait timer resets **per pass**
- Streamed LLM wait progress (Ollama + BYOK); report **Duration** + `{mode}_HHMM` filenames
- Sentinel / partial modes omit unscored audit bands (not `0%`)
- User docs: adaptive UX (FAQ / setup / try-on); Phase A same-`--deep`-pipeline tip complete

### Added (Deep coverage)

- Multi-pass **deep coverage** for LLM runs (default on): heuristics + chunked P1→P3 + checklist coverage tally; `--deep` / `--no-deep` (single-shot)
- **Rules registry** by id (project `.repolens/rules/` → user → packaged defaults)—not hard-coded author-machine Markdown paths
- Graceful structured LLM spine: ask → coerce → micro-repair → degrade; always write a report (exit 0) on schema failure
- Guided script deep Y/n (default Y for review / full-audit; probes CLI help for `--deep`)
- Docs: FAQ deep coverage; setup / try-on tips; Anthropic/OpenAI use the same `--deep` pipeline (Phase A)

### Added (Phase 4 CI & ecosystem)

- GitHub Action (`action.yml`) with `run=auto|dry-run|scanners-only|llm`
- Example workflow + [ci.md](./ci.md) (includes Bitbucket script)
- PyPI Trusted Publishing workflow + [publishing.md](./publishing.md)
- Opt-in local learning: `repolens learn build|status|clear`, FTS index, consent
- Optional extra `repolens[local-ml]`; docs [local-learning.md](./local-learning.md)
- Monorepo example + [review-confidence-log.md](./review-confidence-log.md)

### Added

- Guided review script: `scripts/repolens-guided.sh` / `scripts/repolens_guided.py`
- Review progress feedback: phase lines, `--verbose` detail, LLM wait heartbeats (`--heartbeat`), `--quiet`
- Configurable LLM timeout: `--timeout`, `timeout_seconds` in config, `REPOLENS_TIMEOUT` (Ollama default **900s**)
- Phase 5 adaptive review: unified `.repolens/repolens.sqlite`, fingerprint sync, smaller LLM packs on warm runs, recommended timeout, `--full`, `repolens adaptive status`

### Fixed

- Missing provider errors now probe for Ollama and print `repolens init --provider ollama` + config path
- Empty `--path ""` (e.g. unset `$TARGET`) errors clearly instead of silently reviewing `.`
- `repolens init --provider ollama` uses an **installed** Ollama model (e.g. `qwen2.5:7b`) instead of always defaulting to `llama3.1` (documented in setup / FAQ / try-on-your-repo)

### Changed (docs sync)

- README / FAQ / SECURITY / setup / ADR / issue templates updated for Phases 0–4 complete
- [try-on-your-repo.md](./try-on-your-repo.md): macOS / Linux / Windows + commands for local / GitHub / Bitbucket / HF / git URL (`[username]` placeholders; `jackfrost` only as example); trimmed redundant substitution examples / dogfood OS duplication (self-review hardening PR4)
- [remote-sources.md](./remote-sources.md): expanded per-forge command + auth tables
- [install-extras.md](./install-extras.md) + README/FAQ: `[dev]` / `[scanners]` / `[local-ml]` live in RepoLens `pyproject.toml` (not in reviewed projects); CI guard `tests/test_docs_extras.py`

### Security

- Plugin installs verify SHA-256 for gitleaks/OSV release assets
- Publish workflow pins `pypa/gh-action-pypi-publish` to commit SHA (v1.13.0)
- Action `git-repository` restricted to https GitHub/GitLab/Bitbucket URLs
- Semgrep config overridable via `REPOLENS_SEMGREP_CONFIG` (offline-friendly)
- Dual-review gate process documented in CONTRIBUTING + exported reports under `docs/reviews/`

### Added (Phase 3 scanners)

- Optional scanners: gitleaks, Semgrep, OSV-Scanner (detect PATH / cache)
- `repolens plugins status|list|install` with consent download (`--yes` for CI)
- Review flags: `--scanners`, `--require-scanners`, `--scanners-only`
- Report section **Automated scanners** + JSON `scannerRuns`
- Optional extra `pip install -e ".[scanners]"` (Semgrep via pip)
- Guide: [scanners.md](./scanners.md) · [design/phase-3-scanners.md](./design/phase-3-scanners.md)

### Added

- Initial open-source scaffolding: README, phases tracker, MIT license, contributing docs
- Security and architecture playbooks under `playbooks/`
- Guide for using playbooks without the CLI (`docs/using-playbooks.md`)
- GitHub issue/PR templates and placeholder CI workflow
- Docs reorganized: root keeps `README.md` + `LICENSE`; community docs under `docs/`
- [FAQ](./faq.md): target languages, CLI language, tools/plugins, modes
- [CLI & report schema design](./design/cli-and-report-schema.md) (Phase 0 exit)
- [ADR-01](./adr/01_analysis_runtime_architecture.md) analysis runtime architecture with Mermaid HLD/sequence/component diagrams
- [ADR diagram legend](./adr/_diagram_legend.md) (shared Mermaid colours and prefixes)
- [AI keys, scanners, OWASP/CVE, local learning](./design/ai-keys-scanners-and-local-learning.md) design + FAQ answers

### Changed

- Phase 0 marked complete; CLI implementation language locked to **Python 3.11+**
- FAQ expanded: BYOK vs Ollama, optional scanners, layered OWASP/CVE, opt-in local learning
- Plain-language decision summary for non-technical readers (FAQ + design §5)
- Step-by-step setup guide for cloud AI, local Ollama, and scanners-only ([setup-ai-and-scanners.md](./setup-ai-and-scanners.md))
- Docs and playbooks made vendor-neutral (no editor-specific agent branding)

### Security

- Project `.repolens.toml` cannot override `provider` / `base_url` / `api_key_env` unless `--trust-project-config`
- `api_key_env` allowlisted; symlinks skipped; `report_dir` must stay under project root
- Provider error bodies no longer echoed to the terminal

### Added (Phase 2 remotes)

- `--bitbucket WORKSPACE/REPO` and `--hf` (models/datasets/spaces)
- Auth via `BITBUCKET_TOKEN` / `HF_TOKEN` (anonymous-first)

### Added (Phase 2 MVP)

- `--git-url` and `--github OWNER/REPO` with shallow clone, `--ref`, and temp cleanup
- GitHub auth: `GITHUB_TOKEN` / `GH_TOKEN`, else `gh auth token`
- Remote reports default to `./reports` under the current working directory
- Guide: [remote-sources.md](./remote-sources.md)

### Added (Phase 1 alpha)

- Python package `repolens` (`0.1.0a1`): `review`, `sentinel`, `architecture`, `export`, `init`, `version`
- Finding schema with mandatory Critical/High `impact` + `codeExample`
- OpenAI-compatible / Anthropic / Ollama adapters (BYOK; no embedded keys)
- Markdown + JSON report writers; pytest CI job

### Notes

- Published PyPI install is not tagged yet—install from source. See [phases.md](./phases.md)

## [0.0.0] - 2026-08-04

### Added

- Project bootstrap (pre-release documentation phase)
