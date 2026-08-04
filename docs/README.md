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
| [using-playbooks.md](./using-playbooks.md) | Run reviews today without the CLI |
| [publishing-checklist.md](./publishing-checklist.md) | Publish the repo to GitHub |
| [CHANGELOG.md](./CHANGELOG.md) | User-facing release notes |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | How to contribute |
| [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) | Community standards |
| [SECURITY.md](./SECURITY.md) | How to report vulnerabilities |
| [SUPPORT.md](./SUPPORT.md) | Where to get help |

Playbooks (review instructions) live in [`../playbooks/`](../playbooks/), not here.
