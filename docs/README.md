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
| [for-everyone.md](./for-everyone.md) | Plain-language page for someone who will read a review, not run the tool |
| [phases.md](./phases.md) | Implementation tracker (what’s done / next) |
| [faq.md](./faq.md) | Languages, tools, modes, export, production honesty |
| [rules.md](./rules.md) | What RepoLens checks, why, on/off, and suppressions (`.repolens-ignore`) |
| [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) | Step-by-step: cloud key, local Ollama, scanners only |
| [install-extras.md](./install-extras.md) | What `[dev]` / `[scanners]` / `[local-ml]` install (RepoLens `pyproject.toml`) |
| [command-atlas.md](./command-atlas.md) | **Holy grail:** install → every command → expect / if-then → timings → troubleshooting |
| [which-command.md](./which-command.md) | Which command to run for security, architecture, or clean code, plus editor-plugin mockups |
| [try-on-your-repo.md](./try-on-your-repo.md) | Install + review local / GitHub / Bitbucket / HF / git URL (macOS, Linux, Windows) |
| [polycode-polycoach-loop.md](./polycode-polycoach-loop.md) | PolyCode PolyCoach classroom loop (sibling guide) |
| [remote-sources.md](./remote-sources.md) | Remote commands + auth: `--github`, `--bitbucket`, `--hf`, `--git-url` |
| [scanners.md](./scanners.md) | Optional scanners: plugins install, flags, cache |
| [packs.md](./packs.md) | Optional domain packs (Azure Sentinel / SOAR, …) |
| [packs-quickcheck.md](./packs-quickcheck.md) | Packs: expected CLI output + rough timings |
| [ci.md](./ci.md) | Pull request job and weekly audit for GitHub, Jenkins, Bitbucket, GitLab, CircleCI, Azure DevOps, and Buildkite |
| [publishing.md](./publishing.md) | PyPI Trusted Publisher UI + pre-publish dogfood |
| [local-learning.md](./local-learning.md) | Opt-in on-disk index + memory |
| [review-confidence-log.md](./review-confidence-log.md) | Confidence history template |
| [compare.md](./compare.md) | We audit, they edit — Plan vs Audit vocabulary vs coding-agent harnesses |
| [using-playbooks.md](./using-playbooks.md) | Run reviews via playbooks (with or without the CLI) |
| [publishing-checklist.md](./publishing-checklist.md) | Publish / maintain the GitHub remote |
| [CHANGELOG.md](./CHANGELOG.md) | User-facing release notes |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | How to contribute |
| [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) | Community standards |
| [SECURITY.md](./SECURITY.md) | How to report vulnerabilities |
| [SUPPORT.md](./SUPPORT.md) | Where to get help |

Playbooks (review instructions) live in [`../playbooks/`](../playbooks/), not here.
