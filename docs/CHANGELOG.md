# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once the first release is tagged.

## [Unreleased]

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
