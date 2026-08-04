# Contributing to RepoLens

Thanks for helping make repository reviews clearer and more useful for everyone.

## Ways to contribute

- Improve **playbooks** (`playbooks/`) for clarity, fewer false positives, or language-specific guidance
- Improve **docs** (README, phases tracker, guides)
- Report bugs and propose features via [GitHub Issues](../../issues)
- CLI code, tests, scanners, Action, and local learning (see [phases.md](./phases.md))

## Development setup

1. Fork the repository and create a branch
2. Python 3.11+:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check src tests
```

3. Open a Pull Request against `main`

Docs/playbook-only changes do not require the Python toolchain.

## Pull request guidelines

- Keep PRs focused (one concern per PR when possible)
- Update [phases.md](./phases.md) checkboxes if you complete tracked work
- Update [CHANGELOG.md](./CHANGELOG.md) under “Unreleased” for user-visible changes
- Do not commit secrets, API keys, or live credentials
- Be respectful—follow the [Code of Conduct](./CODE_OF_CONDUCT.md)

### Dual-review gate (maintainers / agents)

Before **commit** or **push** on this repo, run the Cursor **pre-commit dual-review** gate (security → bugs → architecture). Deliver:

1. Chat gate verdict with confidence %  
2. Durable report under `docs/reviews/gate_review_report_YYYY-MM-DD.md` for ship/push  
3. A row in [review-confidence-log.md](./review-confidence-log.md)  

Do **not** skip the gate for “docs-only” or large features. Push still requires an explicit override phrase after a go verdict.

### PR checklist

- [ ] Description explains *why* the change exists
- [ ] Docs/playbooks render clearly in Markdown preview
- [ ] No secrets or personal machine paths required for others to use the change
- [ ] Linked issue (if applicable)
- [ ] Dual-review gate run if this change is being committed/pushed by an agent

## Playbook changes

Playbooks drive review quality. When editing them:

- Prefer evidence-based findings over speculative ones
- Keep **Critical/High → code example** requirements
- Call out CI/scanners as complements, not replacements
- Avoid vendor lock-in or one ecosystem’s idioms unless labeled

## Security issues

Do **not** open a public issue for vulnerabilities in RepoLens itself. See [SECURITY.md](./SECURITY.md).

## Questions

Use GitHub Discussions (when enabled) or an issue with the `question` label.
