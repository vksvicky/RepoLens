# RepoLens

**See into any repository—security, reliability, and architecture—before you ship.**

RepoLens is an open-source CLI that runs structured code reviews against projects you care about: on your machine, or cloned from GitHub, Bitbucket, Hugging Face, or any Git URL. It follows a clear **P1 → P2 → P3** pass (security → bugs/reliability/performance → architecture/quality) and writes audit-friendly reports with impact, remediation steps, and code-example fixes for Critical/High findings.

> **Status:** Phase 0 complete (docs, playbooks, design, ADR). Phase 1 (Python CLI) is next.  
> Tracker: [docs/phases.md](./docs/phases.md) · FAQ: [docs/faq.md](./docs/faq.md) · Architecture: [docs/adr/01_analysis_runtime_architecture.md](./docs/adr/01_analysis_runtime_architecture.md)

---

## Why RepoLens?

| Need | How RepoLens helps |
|------|--------------------|
| Review **any** project, not one vendor’s stack | Local paths + Git remotes |
| Security without ignoring architecture | Full review + `sentinel` security-only mode |
| Actionable findings | Impact, fix plan, **code examples** on Critical/High |
| Shareable audits | Markdown reports (PDF via pandoc / Print) |
| Production honesty | Complements—does not replace—CI, tests, and scanners |

RepoLens is **not** a replacement for Semgrep, CodeQL, Dependabot, Snyk, or your test suite. Those stay in CI. RepoLens adds a consistent, human-readable due-diligence layer you can run anywhere.

---

## Modes (planned)

| Command (planned) | What it does |
|-------------------|--------------|
| `repolens review` | Full dual review: P1 security + P2 reliability + P3 architecture (scoped or full) |
| `repolens sentinel` | **Security-only** scan (P1 playbook)—fast guardrail pass |
| `repolens architecture` | Architecture / production-readiness audit (full playbook) |
| `repolens export` | Export or convert an existing report (e.g. Markdown → PDF if tools allow) |

---

## Languages & tools

- **CLI:** Python 3.11+  
- **Reviews:** language-agnostic, with first-class focus on JS/TS, Python, Go, JVM, C#, Ruby, PHP, Rust, Swift (+ IaC/config)  
- **AI:** Bring your own cloud key **or** run a local model (e.g. Ollama)—no embedded RepoLens key  
- **CVE / SAST / secrets:** optional plugins (OSV, Semgrep, gitleaks)—not forced into the slim install  
- **Local learning (planned):** opt-in, stays on your disk, you are informed first  

Full answers: **[docs/faq.md](./docs/faq.md)** · **[docs/design/ai-keys-scanners-and-local-learning.md](./docs/design/ai-keys-scanners-and-local-learning.md)**.  

**Setup steps (cloud key / local Ollama / scanners):** **[docs/setup-ai-and-scanners.md](./docs/setup-ai-and-scanners.md)**.

---

## Quick start (when the CLI ships)

```bash
# Install (planned)
# pipx install repolens
# # or: uv tool install repolens

# Review a local project
repolens review --path ./my-app

# Security-only
repolens sentinel --path ./my-app

# Remote sources
repolens review --github owner/repo
repolens review --bitbucket workspace/repo
repolens review --hf user/dataset-or-space-repo
repolens review --git-url https://github.com/owner/repo.git --ref main
```

Until then, you can already use the [playbooks](./playbooks/) with any LLM chat that can read your repo (see [docs/using-playbooks.md](./docs/using-playbooks.md)).

---

## Reports

### In the terminal / chat
Summaries show **confidence %**, severity counts, and top findings.

### Saved Markdown (default artifact)
```text
reports/gate_review_report_YYYY-MM-DD.md
```
Each Critical/High finding should include explanation, **impact**, recommended fix, and a **code example**.

### PDF
Markdown is the source of truth. Convert with pandoc when available:

```bash
pandoc reports/gate_review_report_YYYY-MM-DD.md -o reports/gate_review_report_YYYY-MM-DD.pdf
```

Or open the Markdown preview and use **Print → Save as PDF**.

---

## Playbooks

| Playbook | File |
|----------|------|
| Security (P1 / `sentinel`) | [playbooks/security.md](./playbooks/security.md) |
| Architecture (release / full audit) | [playbooks/architecture.md](./playbooks/architecture.md) |

More: [playbooks/README.md](./playbooks/README.md). Contributions: [docs/CONTRIBUTING.md](./docs/CONTRIBUTING.md).

---

## Repository layout

```text
RepoLens/
├── README.md                 # This page (root on purpose)
├── LICENSE                   # MIT
├── playbooks/                # Review instruction sources
├── docs/                     # All other documentation
│   ├── README.md             # Docs index + naming conventions
│   ├── phases.md             # Implementation tracker
│   ├── faq.md                # Languages, tools, common questions
│   ├── design/               # CLI UX & report schema
│   ├── using-playbooks.md
│   └── …                     # CHANGELOG, CONTRIBUTING, SECURITY, …
└── .github/                  # Issue/PR templates, workflows
```

Why some filenames are `UPPERCASE.md` and others are not: see [docs/README.md](./docs/README.md#naming-pattern).

---

## Roadmap at a glance

1. **Phase 0** — Docs, playbooks, design ← **done**
2. **Phase 1** — Core CLI (Python): local path, `review` / `sentinel`, Markdown reports ← *next*
3. **Phase 2** — Remote sources (GitHub, Bitbucket, Hugging Face, generic Git)
4. **Phase 3** — Optional scanner plugins (e.g. gitleaks, Semgrep, OSV)
5. **Phase 4** — CI integrations (GitHub Action, etc.)

Details: **[docs/phases.md](./docs/phases.md)** · Design: **[docs/design/cli-and-report-schema.md](./docs/design/cli-and-report-schema.md)** · ADR: **[docs/adr/01_analysis_runtime_architecture.md](./docs/adr/01_analysis_runtime_architecture.md)**.

---

## Contributing

- [docs/CONTRIBUTING.md](./docs/CONTRIBUTING.md)
- [docs/CODE_OF_CONDUCT.md](./docs/CODE_OF_CONDUCT.md)
- [docs/SECURITY.md](./docs/SECURITY.md) for vulnerability reports
- [docs/SUPPORT.md](./docs/SUPPORT.md)

---

## License

[MIT](./LICENSE) — use it, fork it, adapt the playbooks for your org.
