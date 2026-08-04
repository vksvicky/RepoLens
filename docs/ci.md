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

### Recommended default (`run: auto`)

- Always runs enabled scanners when tools resolve  
- Runs the LLM review **only** if a key secret is present (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, or `REPOLENS_API_KEY`)  
- Without a key → `--scanners-only`

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

### Inputs

| Input | Default | Notes |
|-------|---------|-------|
| `path` | `.` | Consumer workspace path |
| `mode` | `review` | `review` \| `sentinel` \| `architecture` |
| `run` | `auto` | See above |
| `fail-on` | `HIGH` | Empty string disables |
| `scanners` | `auto` | Same as CLI |
| `require-scanners` | `false` | |
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

## Related

- [scanners.md](./scanners.md)  
- [setup-ai-and-scanners.md](./setup-ai-and-scanners.md)  
- [publishing.md](./publishing.md) — PyPI releases for `install-from: pypi`  
