# Playbooks

These Markdown files are the **source of truth** for RepoLens review quality.

| File | Used by (CLI) | Purpose |
|------|------------------------|---------|
| [security.md](./security.md) | `repolens sentinel`, and P1 of `repolens review` | Security analysis |
| [architecture.md](./architecture.md) | `repolens architecture`, P3 / full audits | Architecture & production readiness |

## Rules of the road

- Critical and High findings must include **impact** and a **code example** fix.
- Prefer evidence from real code paths over speculation.
- Call out gaps in tests/CI/scanners; do not pretend LLM review replaces them.
- Keep guidance portable across languages and hosts (local, GitHub, Bitbucket, Hugging Face, etc.).
- Language support tiers (first-class vs best-effort): [docs/faq.md](../docs/faq.md).

Improvements welcome via PR—see [docs/CONTRIBUTING.md](../docs/CONTRIBUTING.md).
