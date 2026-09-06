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
          sarif: "true"         # Phase 6.4 anchored SARIF (default)
          pr-summary: "true"    # Phase 6.8 job summary + annotations (default)
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

### PR suggested-fix summary (Phase 6.8)

After review, the Action (when `pr-summary: true`) runs:

```bash
repolens pr-summary --reports-dir reports --github-summary --annotate
```

- Appends a **Critical/High** suggested-fix section to the job’s `$GITHUB_STEP_SUMMARY` (code examples included; no auto-commit)
- Emits GitHub workflow commands: `::error` for Critical, `::warning` for High (file/line when the path is safe)
- Does **not** post PR review comments via the GitHub API

Local / other CI:

```bash
repolens review --ci --scanners auto --fail-on HIGH --format both --sarif --out reports
repolens pr-summary --reports-dir reports          # Markdown to stdout
repolens pr-summary --reports-dir reports --annotate   # also print ::error / ::warning
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
| `sarif` | `true` | Write anchored SARIF |
| `pr-summary` | `true` | Job summary + `::error`/`::warning` annotations |
| `reports-dir` | `reports` | Output directory under `path` |
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
          - repolens plugins install all --yes
          - |
            python - <<'PY'
            import os, subprocess
            from repolens.ci_args import build_review_argv
            argv = build_review_argv(
                mode="review",
                path=".",
                run=os.environ.get("REPOLENS_RUN", "auto"),
                fail_on=os.environ.get("REPOLENS_FAIL_ON", "HIGH"),
                require_scanners=True,
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

## Anchored SARIF + SBOM (Phase 6.4 / 6.2)

```bash
repolens review --ci --scanners auto --fail-on HIGH --format both --sarif
# writes reports/*.sarif.json (verified locations only) + sbom.cdx.json when Trivy is available
```

**SARIF rule:** scanner findings use trusted file/line; LLM/heuristic findings are included **only** when `anchorQuote` resolves in the cited file. Unresolved locations stay in Markdown/JSON with a “location unverified” note — they are **never** emitted to SARIF.

### Upload to GitHub code scanning (GHAS)

```yaml
      - uses: vksvicky/RepoLens@main
        with:
          path: .
          run: auto
          fail-on: HIGH
          ci: "true"
      - name: RepoLens SARIF (optional local CLI)
        if: always()
        run: |
          repolens review --path . --ci --scanners-only --sarif --fail-on "" || true
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: reports/
          # or a single reports/*.sarif.json path
```

Sonar / other ASPM: ingest the same SARIF as an external issues file, or archive `reports/**` (JSON + SARIF + `sbom.cdx.json`) as CI artifacts. RepoLens does **not** host an ASPM portal.

Design: [phase-6.x §6.4](./design/phase-6.x-scanner-depth-ci-gates-and-credibility.md)

## Adaptive cache in CI

Ephemeral agents usually start **cold**. Prefer:

```toml
# .repolens.toml on the CI agent / checked in for CI profiles
[adaptive]
enabled = false
```

Or wipe `.repolens/` at the start of each job.

**Warm packs (optional):** restore and save `.repolens/repolens.sqlite` with your CI cache, keyed by **repo + branch** (never share one DB across unrelated repositories on a multi-tenant agent). Fingerprints are path/hash only; do **not** enable content FTS learning (`repolens learn`) on shared CI disks without a retention policy.

Long-lived / shared agents: treat `.repolens/` as workspace-local; clean between unrelated jobs.

Design: [phase-7-enterprise-ci-and-report-delivery.md](./design/phase-7-enterprise-ci-and-report-delivery.md).

## Corporate CI (Phase 7)

GitHub Action and Bitbucket (above) remain first-class. Phase 7 adds **Jenkins**, **CircleCI**, and **GitLab CI** recipes plus delivery patterns. RepoLens does **not** ship a hosted dashboard — archive `reports/**` and plug into your tools.

Shared CLI shape for PR / merge gates (prefer scanners; optional LLM when a key is present):

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install "repolens[scanners] @ git+https://github.com/vksvicky/RepoLens.git@main"
# After PyPI alpha (#1): pip install "repolens[scanners]==0.1.0a1"
repolens plugins install all --yes
repolens review --path . --out ./reports --format both --sarif \
  --ci --scanners auto --fail-on HIGH --require-scanners
# Exit 1 → fail-on threshold · exit 2 → missing scanners / usage.
# Prefer --scanners-only when policy forbids sending code to cloud LLMs.
# Do not soft-ignore plugins install in CI — a silent scanner miss skips the gate.
```

Artifacts typically include:

| Artifact | Notes |
|----------|--------|
| `reports/gate_review_report_*.md` | Human gate report |
| `reports/*.json` | `FindingReport` JSON (`--format both`) |
| `reports/*.sarif.json` | Anchored SARIF (`--sarif`) |
| `reports/sbom.cdx.json` | CycloneDX when Trivy is available |

Treat report Markdown/JSON as **internal** — they may contain paths and code excerpts.

### Jenkins (Declarative Pipeline)

```groovy
pipeline {
  agent any
  environment {
    // Optional — omit for scanners-only / private Ollama runners
    OPENAI_API_KEY = credentials('openai-api-key')
  }
  stages {
    stage('RepoLens') {
      steps {
        sh '''#!/usr/bin/env bash
          set -euo pipefail
          python3 -m venv .venv
          . .venv/bin/activate
          pip install -U pip
          pip install "repolens[scanners] @ git+https://github.com/vksvicky/RepoLens.git@main"
          # After PyPI alpha (#1): pip install "repolens[scanners]==0.1.0a1"
          repolens plugins install all --yes
          # Prefer scanners-only when no cloud key / policy forbids LLM egress:
          #   --scanners-only
          repolens review --path . --out ./reports --format both --sarif \
            --ci --scanners auto --fail-on HIGH --require-scanners
        '''
      }
    }
  }
  post {
    // Archive even when --fail-on exits 1 (gate failure is when reports matter most)
    always {
      archiveArtifacts artifacts: 'reports/**', fingerprint: true, allowEmptyArchive: true
      // Optional: email via Jenkins Email Extension / corporate SMTP (RepoLens has no SMTP)
      // emailext(
      //   subject: "RepoLens ${env.JOB_NAME} #${env.BUILD_NUMBER}",
      //   body: "See attached gate report / build artifacts.",
      //   attachmentsPattern: 'reports/gate_review_report_*.md',
      //   to: '${DEFAULT_RECIPIENTS}'
      // )
    }
  }
}
```

Exit codes: `0` success · `1` `--fail-on` hit · `2` usage · see [Exit codes](#exit-codes).

### CircleCI

```yaml
version: 2.1
jobs:
  repolens:
    docker:
      - image: cimg/python:3.12
    steps:
      - checkout
      - run:
          name: Install RepoLens
          command: |
            pip install -U pip
            pip install "repolens[scanners] @ git+https://github.com/vksvicky/RepoLens.git@main"
            # After PyPI alpha (#1): pip install "repolens[scanners]==0.1.0a1"
            repolens plugins install all --yes
      - run:
          name: Review
          command: |
            repolens review --path . --out ./reports --format both --sarif \
              --ci --scanners auto --fail-on HIGH --require-scanners
      - store_artifacts:
          path: reports
workflows:
  security:
    jobs:
      - repolens
```

Store API keys as CircleCI **project** or **context** environment variables — never commit them.

### GitLab CI

```yaml
repolens:
  image: python:3.12-slim
  stage: test
  variables:
    PIP_DISABLE_PIP_VERSION_CHECK: "1"
  before_script:
    - pip install -U pip
    - pip install "repolens[scanners] @ git+https://github.com/vksvicky/RepoLens.git@main"
    # After PyPI alpha (#1): pip install "repolens[scanners]==0.1.0a1"
    - repolens plugins install all --yes
  script:
    - |
      repolens review --path . --out ./reports --format both --sarif \
        --ci --scanners auto --fail-on HIGH --require-scanners
  artifacts:
    when: always
    paths:
      - reports/
    expire_in: 14 days
```

Use GitLab **CI/CD variables** (masked/protected) for LLM keys. `artifacts: when: always` keeps reports even when `--fail-on` fails the job.

### Azure DevOps (stretch)

Nice-to-have only — not a Phase 7 exit criterion:

```yaml
# azure-pipelines.yml (sketch)
pool:
  vmImage: ubuntu-latest
steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: "3.12"
  - script: |
      pip install "repolens[scanners] @ git+https://github.com/vksvicky/RepoLens.git@main"
      # After PyPI alpha (#1): pip install "repolens[scanners]==0.1.0a1"
      repolens plugins install all --yes
      repolens review --path . --out ./reports --format both --sarif \
        --ci --scanners auto --fail-on HIGH --require-scanners
    displayName: RepoLens
    env:
      OPENAI_API_KEY: $(OPENAI_API_KEY)
  - task: PublishBuildArtifacts@1
    inputs:
      PathtoPublish: reports
      ArtifactName: repolens-reports
    condition: always()
```

### Email notification

RepoLens does **not** run an SMTP server. Attach `reports/gate_review_report_*.md` (and optionally JSON) via:

- Jenkins `emailext` / Email Extension (see comment in Jenkinsfile above)
- GitLab/CircleCI email integrations or a post-job script to your corporate relay
- Forge “notify on failure” with a link to the archived artifact

### Slack / Teams webhook (summary only)

Post **counts + artifact URL** only — never code excerpts, secrets, or full finding bodies.

```bash
# After a successful artifact upload, with REPORTS_DIR=reports and WEBHOOK_URL set:
python3 - <<'PY'
import json, os, urllib.request
from pathlib import Path

reports = Path(os.environ.get("REPORTS_DIR", "reports"))
# Exclude *.sarif.json (same rule as pr_summary / explain report discovery)
candidates = sorted(
    p for p in reports.glob("*.json") if not p.name.endswith(".sarif.json")
)
if not candidates:
    raise SystemExit("no FindingReport JSON under reports/")
data = json.loads(candidates[-1].read_text(encoding="utf-8"))
# Prefer explicit schema fields; missing keys → 0 / unknown rather than None%
summary = data.get("summary") or {}
conf = data.get("confidence")
conf_s = f"{conf}%" if isinstance(conf, int) else "n/a"
payload = {
    "text": (
        f"RepoLens gate {conf_s} — "
        f"Critical {summary.get('critical', 0)} · "
        f"High {summary.get('high', 0)} · "
        f"Medium {summary.get('medium', 0)} · "
        f"Low {summary.get('low', 0)}. "
        f"Artifacts: {os.environ.get('ARTIFACT_URL', '(see CI artifacts)')}"
    )
}
req = urllib.request.Request(
    os.environ["WEBHOOK_URL"],
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
urllib.request.urlopen(req, timeout=30)
PY
```

### Dashboard ingest (DefectDojo / custom)

Use `--format json|both` and ingest `FindingReport` JSON (and/or anchored SARIF) into your ASPM / DefectDojo / internal portal. Schema lives in the product (`src/repolens/schema.py`). RepoLens does **not** host a multi-tenant dashboard in Phase 7.

### Forge push protection vs RepoLens

| Layer | Role |
|-------|------|
| **GitHub / GitLab secret push protection** (and similar) | Blocks **pre-receive** commits that contain known secrets |
| **RepoLens** | Audits **landed / PR** code with scanners + optional LLM; fails the **CI job** via `--fail-on` |

Use both: forge push protection stops secret leaks at the gate; RepoLens reviews what already reached the branch or merge request. RepoLens is **not** a pre-receive server.

Checklist: [phase-7-execution-checklist.md](./design/phase-7-execution-checklist.md) · design: [phase-7-enterprise-ci-and-report-delivery.md](./design/phase-7-enterprise-ci-and-report-delivery.md).

## Related

- [scanners.md](./scanners.md)  
- [setup-ai-and-scanners.md](./setup-ai-and-scanners.md)  
- [publishing.md](./publishing.md) — PyPI releases for `install-from: pypi`  
- [faq.md](./faq.md) — *Corporate CI/CD & delivery*  
- [phase-7-enterprise-ci-and-report-delivery.md](./design/phase-7-enterprise-ci-and-report-delivery.md) — enterprise delivery design  

