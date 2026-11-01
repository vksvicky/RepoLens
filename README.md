# RepoLens

**See into any repository—security, reliability, and architecture—before you ship.**

RepoLens is an open-source CLI for a structured review of a project on your machine, or cloned from GitHub, Bitbucket, Hugging Face, or any Git URL. It runs **P1 → P2 → P3** (security, then bugs and reliability, then architecture) and writes a Markdown report. Critical and High findings include impact, a fix, and a code example.

It is a local CLI. There is no hosted dashboard. Scanners, tests, and your existing CI stay in place. RepoLens adds one portable report you can run anywhere.

> **`repolens-audit==0.1.6.post1`** · CLI: `repolens` · Python 3.11+  
> [Sample report](https://github.com/vksvicky/RepoLens/blob/main/reports/samples/sample_audit_report.md) · [PDF](https://github.com/vksvicky/RepoLens/blob/main/reports/samples/sample_audit_report.pdf) · [Phase tracker](https://github.com/vksvicky/RepoLens/blob/main/docs/phases.md)

A report is evidence, not a “% secure” score. If you will read the report and not run the tool, start with [RepoLens in plain language](https://github.com/vksvicky/RepoLens/blob/main/docs/for-everyone.md).

## Install and run

```bash
pip install "repolens-audit[scanners]==0.1.6.post1"
repolens which pr
repolens review --preset pr --path .
```

`pr` runs scanners and does not call a model. `repolens which audit` prints the full due-diligence command. The other names are `changed`, `release`, `security`, and `architecture`. An unknown name exits 2 and lists the names.

Each report records the command you typed and the flags that actually ran.

From a clone, for contributors: `pip install -e ".[dev]"`. Optional extras (`scanners`, `dev`, `local-ml`) are in [install-extras.md](https://github.com/vksvicky/RepoLens/blob/main/docs/install-extras.md).

## Commands

| Command | What it does |
|---------|--------------|
| `repolens which` | Print the command for `pr`, `changed`, `release`, `audit`, `security`, or `architecture` |
| `repolens review` | Full review: P1 + P2 + P3 |
| `repolens audit` | Due diligence in one command (`--preset release`, plus the ratchet and verify) |
| `repolens sentinel` | Security only (P1) |
| `repolens architecture` | Architecture and production readiness |
| `repolens init` | Choose a cloud key, Ollama, or no model |
| `repolens plugins` | Optional scanners: `status`, `list`, `install` |
| `repolens explain` | One finding, with a diagram |
| `repolens export` | Convert a report (PDF needs pandoc) |
| `repolens check --diff` | Cyclicity ratchet for CI. Baseline: `repolens baseline` |

What is checked, and how to turn a rule off: [rules.md](https://github.com/vksvicky/RepoLens/blob/main/docs/rules.md).

## A review in one sitting

```bash
repolens init --provider ollama    # or openai, anthropic, deepseek, none
repolens review --path ./my-app --dry-run
repolens plugins install all
repolens review --path ./my-app --scanners-only
repolens review --path ./my-app
```

Cloud, Ollama, or scanners-only: [setup-ai-and-scanners.md](https://github.com/vksvicky/RepoLens/blob/main/docs/setup-ai-and-scanners.md).

Remotes use the same `review` command:

```bash
repolens review --github owner/repo --ref main --dry-run
repolens review --bitbucket workspace/repo --ref main --dry-run
repolens review --hf org/model --dry-run
repolens review --git-url https://github.com/owner/repo.git --ref main --dry-run
```

Private remotes use `GITHUB_TOKEN`, `BITBUCKET_TOKEN`, or `HF_TOKEN`. Walkthrough for macOS, Linux, and Windows, including the interactive helper: [try it on your repo](https://github.com/vksvicky/RepoLens/blob/main/docs/try-on-your-repo.md#guided-review-interactive).

The report lands at `reports/gate_review_report_{mode}_YYYY-MM-DD_HHMM.md`.

## GitHub Action

```yaml
- uses: actions/checkout@v7
- uses: vksvicky/RepoLens@v0.1.6.post1
  with:
    path: .
    run: auto
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}  # optional
```

`run: auto` always runs scanners, and calls a model only when a key is set. Jenkins, GitLab, Bitbucket, and the weekly audit are in [ci.md](https://github.com/vksvicky/RepoLens/blob/main/docs/ci.md).

## Documentation

| | |
|---|---|
| Try it, including the guided script | [try-on-your-repo.md](https://github.com/vksvicky/RepoLens/blob/main/docs/try-on-your-repo.md#guided-review-interactive) |
| Cloud, Ollama, scanners | [setup-ai-and-scanners.md](https://github.com/vksvicky/RepoLens/blob/main/docs/setup-ai-and-scanners.md) |
| FAQ | [faq.md](https://github.com/vksvicky/RepoLens/blob/main/docs/faq.md) |
| Rules | [rules.md](https://github.com/vksvicky/RepoLens/blob/main/docs/rules.md) |
| CI | [ci.md](https://github.com/vksvicky/RepoLens/blob/main/docs/ci.md) |
| Remotes | [remote-sources.md](https://github.com/vksvicky/RepoLens/blob/main/docs/remote-sources.md) |
| Scanners | [scanners.md](https://github.com/vksvicky/RepoLens/blob/main/docs/scanners.md) |
| Phase tracker | [phases.md](https://github.com/vksvicky/RepoLens/blob/main/docs/phases.md) |
| Playbooks | [security](https://github.com/vksvicky/RepoLens/blob/main/playbooks/security.md) · [architecture](https://github.com/vksvicky/RepoLens/blob/main/playbooks/architecture.md) |
| Contributing | [CONTRIBUTING.md](https://github.com/vksvicky/RepoLens/blob/main/docs/CONTRIBUTING.md) · [security reports](https://github.com/vksvicky/RepoLens/blob/main/docs/SECURITY.md) |

## Disclaimer

Findings can be wrong. You verify them before you act. A report is not a certification. The full text is in every Markdown report and in the [FAQ](https://github.com/vksvicky/RepoLens/blob/main/docs/faq.md#disclaimer-ai--llm-output).

## License

[MIT](https://github.com/vksvicky/RepoLens/blob/main/LICENSE).
