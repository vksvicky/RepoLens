# Contributing to RepoLens

Thanks for helping make repository reviews clearer and more useful for everyone.

## Ways to contribute

- Improve **playbooks** (`playbooks/`) for clarity, fewer false positives, or language-specific guidance
- Improve **docs** (README, phases tracker, guides)
- Report bugs and propose features via [GitHub Issues](../../issues)
- Later: CLI code, tests, and scanner plugins (see [phases.md](./phases.md))

## Development setup (docs-only phase)

Right now the repo is documentation + playbooks. To contribute:

1. Fork the repository
2. Create a branch: `git checkout -b docs/short-description`
3. Make your changes
4. Open a Pull Request against `main`

When the CLI lands, this section will add language-specific install and test commands.

## Pull request guidelines

- Keep PRs focused (one concern per PR when possible)
- Update [phases.md](./phases.md) checkboxes if you complete tracked work
- Update [CHANGELOG.md](./CHANGELOG.md) under “Unreleased” for user-visible changes
- Do not commit secrets, API keys, or live credentials
- Be respectful—follow the [Code of Conduct](./CODE_OF_CONDUCT.md)

### PR checklist

- [ ] Description explains *why* the change exists
- [ ] Docs/playbooks render clearly in Markdown preview
- [ ] No secrets or personal machine paths required for others to use the change
- [ ] Linked issue (if applicable)

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
