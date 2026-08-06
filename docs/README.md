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
| [rules.md](./rules.md) | What RepoLens checks, why, and how to turn rules on/off (plain language) |
| [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) | Step-by-step: cloud key, local Ollama, scanners only |
| [install-extras.md](./install-extras.md) | What `[dev]` / `[scanners]` / `[local-ml]` install (RepoLens `pyproject.toml`) |
| [try-on-your-repo.md](./try-on-your-repo.md) | Install + review local / GitHub / Bitbucket / HF / git URL (macOS, Linux, Windows) |
| [remote-sources.md](./remote-sources.md) | Remote commands + auth: `--github`, `--bitbucket`, `--hf`, `--git-url` |
| [scanners.md](./scanners.md) | Optional scanners: plugins install, flags, cache |
| [ci.md](./ci.md) | GitHub Action + Bitbucket CI script |
| [publishing.md](./publishing.md) | PyPI Trusted Publisher UI + pre-publish dogfood |
| [local-learning.md](./local-learning.md) | Opt-in on-disk index + memory |
| [review-confidence-log.md](./review-confidence-log.md) | Confidence history template |
| [design/phase-2-multi-source-ingest.md](./design/phase-2-multi-source-ingest.md) | Phase 2 MVP design decisions |
| [design/phase-3-scanners.md](./design/phase-3-scanners.md) | Phase 3 scanner plugin decisions |
| [design/phase-4-ci-and-ecosystem.md](./design/phase-4-ci-and-ecosystem.md) | Phase 4 CI Action, PyPI, local learning |
| [design/phase-5-adaptive-cache-and-recommendations.md](./design/phase-5-adaptive-cache-and-recommendations.md) | Phase 5 design: fingerprint cache, progressive review, per-project timeout |
| [design/phase-5.1-deep-hardening.md](./design/phase-5.1-deep-hardening.md) | Phase 5.1: honest coverage, security audit confidence, quieter deep reports |
| [design/phase-6-issue-explain-diagrams.md](./design/phase-6-issue-explain-diagrams.md) | Phase 6: UUID explain + foolproof Mermaid diagrams |
| [design/phase-6.x-scanner-depth-ci-gates-and-credibility.md](./design/phase-6.x-scanner-depth-ci-gates-and-credibility.md) | Phase 6.1–6.10: scanners/SBOM/gates/SARIF (core) + feedback/PR UX/reachability/domain packs (extended) |
| [benchmarks/methodology.md](./benchmarks/methodology.md) | Pre-registered benchmark: remediation rate / MTTR lead (Phase 6.6) |
| [benchmarks/results/mvp-2026-08-06.md](./benchmarks/results/mvp-2026-08-06.md) | MVP results (partial dogfood; formal study TBD) |
| [superpowers/plans/2026-08-06-enterprise-ci-triage-routing.md](./superpowers/plans/2026-08-06-enterprise-ci-triage-routing.md) | Plan: CI triage routing (LLM only on scanner hits) for large repos |
| [blog-ideas/enterprise-scale-llm-review-ci.md](./blog-ideas/enterprise-scale-llm-review-ci.md) | Blog draft: why 10k-file repos cannot full-LLM on every PR |
| [design/phase-7-enterprise-ci-and-report-delivery.md](./design/phase-7-enterprise-ci-and-report-delivery.md) | Phase 7 design: Jenkins/CircleCI, artifacts, email/dashboard (not SaaS) |
| [design/cli-and-report-schema.md](./design/cli-and-report-schema.md) | CLI UX, exit codes, finding/report schema |
| [design/ai-keys-scanners-and-local-learning.md](./design/ai-keys-scanners-and-local-learning.md) | AI keys, OWASP/CVE layers, bundled vs optional scanners, local ML |
| [design/repolens-vs-appsec-tools.md](./design/repolens-vs-appsec-tools.md) | Honest comparison vs Checkmarx, Snyk, Semgrep, CodeQL, Trivy, … (product positioning) |
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
