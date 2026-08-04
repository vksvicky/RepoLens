# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once the first release is tagged.

## [Unreleased]

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
- [try-on-your-repo.md](./try-on-your-repo.md): macOS / Linux / Windows + commands for local / GitHub / Bitbucket / HF / git URL (`[username]` placeholders; `jackfrost` only as example)
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
