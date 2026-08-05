# Security Policy

## Supported versions

RepoLens is in early development. Security fixes will target the latest `main` branch until the first tagged release. After releases exist, this table will list supported versions.

| Version | Supported |
|---------|-----------|
| `main`  | Yes       |
| < 0.1.0 | N/A (pre-release) |

## Reporting a vulnerability

If you discover a security issue in **RepoLens itself** (CLI, CI action, docs that leak secrets, dependency issues in this repo):

1. **Do not** open a public GitHub issue.
2. Use [GitHub Private Vulnerability Reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) on the [RepoLens repository](https://github.com/vksvicky/RepoLens) (preferred and currently the only public contact path).

Please include:

- Description of the issue and impact
- Steps to reproduce
- Affected commit / version if known
- Any suggested fix

We aim to acknowledge reports within **7 days** and to keep you updated on remediation.

## Scope notes

- Findings produced **by** RepoLens against *other* codebases are not “vulnerabilities in RepoLens”—report those to the owners of that code.
- Never paste live production secrets into issues, PRs, or playbook examples. Use placeholders.

## Safe contribution defaults

- Prefer `*.example` env files
- Add secret patterns to `.gitignore`
- Do not commit API keys for LLM providers or forge tokens

## AI keys, code privacy, and local learning

Product behaviour (for operators of the CLI):

| Topic | Policy |
|-------|--------|
| API keys | Bring your own; store in env / secret store — never in reports or git |
| Cloud LLM | Code excerpts in prompts go to **your chosen provider** under their terms |
| Local LLM | Supported path (e.g. Ollama) so reviews need not leave the machine |
| Local learning (shipped) | Opt-in index/memory under `.repolens/`; **no** upload to a RepoLens training service; informed consent on enable (`repolens learn`) |
| Scanners | Optional plugins; do not require cloud accounts for gitleaks/Semgrep/OSV-style tools |

Details: [local-learning.md](./local-learning.md) · [design/ai-keys-scanners-and-local-learning.md](./design/ai-keys-scanners-and-local-learning.md) · [faq.md](./faq.md).
