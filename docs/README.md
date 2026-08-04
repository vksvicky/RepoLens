# Documentation

User and contributor docs for RepoLens. The only files that must stay at the **repository root** are `README.md` (GitHub landing page) and `LICENSE` (license detection).

## Naming pattern

| Kind | Naming | Where | Why |
|------|--------|--------|-----|
| Landing + license | `README.md`, `LICENSE` | **Root** | GitHub shows README; detects LICENSE |
| Community health | `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md` | **`docs/`** (or `.github/`) | [GitHub looks for these exact names](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/creating-a-default-community-health-file) in `/`, `/docs`, or `/.github` — **uppercase is intentional** |
| Changelog | `CHANGELOG.md` | `docs/` | [Keep a Changelog](https://keepachangelog.com/) convention |
| Everything else | `kebab-case.md` | `docs/` | Normal docs — **not** shouted in CAPS |

So: CAPS is not “all docs.” It is only for a small set of well-known meta filenames so tools and humans recognize them.

## Index

| Doc | Purpose |
|-----|---------|
| [phases.md](./phases.md) | Implementation tracker (what’s done / next) |
| [faq.md](./faq.md) | Languages, tools, modes, export, production honesty |
| [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) | Step-by-step: cloud key, local Ollama, scanners only |
| [remote-sources.md](./remote-sources.md) | Clone remotes: `--github`, `--git-url`, auth, reports |
| [design/phase-2-multi-source-ingest.md](./design/phase-2-multi-source-ingest.md) | Phase 2 MVP design decisions |
| [design/cli-and-report-schema.md](./design/cli-and-report-schema.md) | CLI UX, exit codes, finding/report schema |
| [design/ai-keys-scanners-and-local-learning.md](./design/ai-keys-scanners-and-local-learning.md) | AI keys, OWASP/CVE layers, bundled vs optional scanners, local ML |
| [adr/](./adr/) | ADRs + diagram legend (how analysis works) |
| [adr/01_analysis_runtime_architecture.md](./adr/01_analysis_runtime_architecture.md) | Pipeline, modes, security zones (diagrams) |
| [using-playbooks.md](./using-playbooks.md) | Run reviews via playbooks (with or without the CLI) |
| [publishing-checklist.md](./publishing-checklist.md) | Publish / maintain the GitHub remote |
| [CHANGELOG.md](./CHANGELOG.md) | User-facing release notes |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | How to contribute |
| [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) | Community standards |
| [SECURITY.md](./SECURITY.md) | How to report vulnerabilities |
| [SUPPORT.md](./SUPPORT.md) | Where to get help |

Playbooks (review instructions) live in [`../playbooks/`](../playbooks/), not here.
