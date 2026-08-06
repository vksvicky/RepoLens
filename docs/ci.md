# Running RepoLens in CI

Use the official **GitHub Action** (composite) or a small shell script (Bitbucket Pipelines, generic CI).

Design: [design/phase-4-ci-and-ecosystem.md](./design/phase-4-ci-and-ecosystem.md)

## GitHub Actions

### Minimal (dry-run)

```yaml
jobs:
  repolens:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: vksvicky/RepoLens@main   # or @v0.1.0a1 when tagged
        with:
          path: .
          run: dry-run
          fail-on: ""
          install-plugins: "false"
```

### Recommended default (`run: auto` + triage)

- Always runs enabled scanners when tools resolve  
- **`--ci` (Action default):** triage routing — LLM **bypassed** when scanners are clean at the severity floor; on hits, LLM runs on hit files only (not a full-repo deep)  
- Runs the LLM path **only** if a key secret is present (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, or `REPOLENS_API_KEY`)  
- Without a key → `--scanners-only` (still gated by `--fail-on`)  
- **`--fail-on` in CI** prefers **scanner-sourced** findings (LLM narrative does not sole-gate the build)

```yaml
jobs:
  repolens:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: vksvicky/RepoLens@main
        with:
          path: .
          mode: review          # or sentinel | architecture
          run: auto             # dry-run | scanners-only | llm | auto
          fail-on: HIGH
          scanners: auto
          ci: "true"            # Phase 6.3 triage (default)
          install-from: local   # install the Action’s own checkout (default)
          install-plugins: "true"
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}  # optional
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: repolens-reports
          path: reports/
```

### Enterprise PR recipe (CLI)

```bash
repolens review --ci --scanners auto --fail-on HIGH --format both
# equivalent intent: scanners gate; LLM explains hit snippets only; no full-tree deep
```

Full `--deep` reviews are for **scheduled / release audits**, not every PR. Budget honesty: clean PRs are typically scanners-only (seconds–minutes); do not assume a hard “&lt;5 minutes” SLA when the model runs.

Design: [phase-6.x §6.3](./design/phase-6.x-scanner-depth-ci-gates-and-credibility.md) · plan: [enterprise-ci-triage-routing](./superpowers/plans/2026-08-06-enterprise-ci-triage-routing.md) · blog: [enterprise-scale-llm-review-ci](./blog-ideas/enterprise-scale-llm-review-ci.md)

### Inputs

| Input | Default | Notes |
|-------|---------|-------|
| `path` | `.` | Consumer workspace path |
| `mode` | `review` | `review` \| `sentinel` \| `architecture` |
| `run` | `auto` | See above |
| `fail-on` | `HIGH` | Empty string disables; with `ci`, scanner findings only |
| `scanners` | `auto` | Same as CLI |
| `require-scanners` | `false` | |
| `ci` | `true` | Triage routing (`--ci`) |
| `install-from` | `local` | `local` (action checkout) \| `pypi` \| `git` |
| `version` | `0.1.0a1` | Used when `install-from=pypi` |
| `install-plugins` | `true` | `repolens plugins install all --yes` |

Reference workflow in this repo: [`.github/workflows/repolens-example.yml`](../.github/workflows/repolens-example.yml) · Action: [`action.yml`](../action.yml)

## Bitbucket Pipelines (script)

```yaml
image: python:3.12

pipelines:
  default:
    - step:
        name: RepoLens
        script:
          - pip install "repolens[scanners] @ git+https://github.com/vksvicky/RepoLens.git@main"
          - repolens plugins install all --yes || true
          - |
            python - <<'PY'
            import os, subprocess
            from repolens.ci_args import build_review_argv
            argv = build_review_argv(
                mode="review",
                path=".",
                run=os.environ.get("REPOLENS_RUN", "auto"),
                fail_on=os.environ.get("REPOLENS_FAIL_ON", "HIGH"),
            )
            raise SystemExit(subprocess.call(argv))
            PY
        artifacts:
          - reports/**
```

Set repository variables / secured variables for API keys the same way as other CI secrets.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | `--fail-on` threshold hit |
| 2 | Usage / missing required scanners / `run=llm` without key |
| 3 | Source/clone error |
| 4 | LLM/provider error |

## Adaptive cache in CI

Ephemeral agents usually start cold. Prefer `[adaptive] enabled = false` in CI, or restore/save `.repolens/repolens.sqlite` with your CI cache if you want warm packs. Details: [design/phase-7-enterprise-ci-and-report-delivery.md](./design/phase-7-enterprise-ci-and-report-delivery.md).

## Corporate CI (Phase 7 — design)

**Today:** GitHub Action + Bitbucket script (above) are the supported first-class docs.

**Next (Phase 7):** Jenkins, CircleCI, GitLab examples; email/webhook/dashboard handoff from `reports/**` artifacts — see [design/phase-7-enterprise-ci-and-report-delivery.md](./design/phase-7-enterprise-ci-and-report-delivery.md). RepoLens does not ship a hosted dashboard; export JSON/Markdown and plug into your tools.

## Related

- [scanners.md](./scanners.md)  
- [setup-ai-and-scanners.md](./setup-ai-and-scanners.md)  
- [publishing.md](./publishing.md) — PyPI releases for `install-from: pypi`  
- [phase-7-enterprise-ci-and-report-delivery.md](./design/phase-7-enterprise-ci-and-report-delivery.md) — enterprise delivery design  

