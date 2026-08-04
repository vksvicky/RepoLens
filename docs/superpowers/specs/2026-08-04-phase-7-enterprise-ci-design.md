# Phase 7 — Enterprise CI/CD & report delivery (design)

**Status:** Design sketch (not implemented)  
**Date:** 2026-08-04  
**Depends on:** Phase 4 Action/CI docs, Phase 5 adaptive cache (local-first)

## 1. Problem

Phases 0–5 make RepoLens usable **locally** and in **GitHub Actions** / a Bitbucket script. Corporate teams also need a clear, production-minded path for:

- Running on a **CI agent** (Jenkins, CircleCI, GitLab CI, Azure DevOps, …) where the repo is checked out on the server  
- **Failing the build** on severity thresholds  
- **Exporting** Markdown/JSON reports to email, chat, artifact stores, or an internal dashboard  

This phase documents that target without shipping a SaaS product yet.

## 2. What is already production-usable (today)

| Use case | Status | Docs |
|----------|--------|------|
| Local developer / security review | **Supported** | [try-on-your-repo.md](../try-on-your-repo.md), [setup-ai-and-scanners.md](../setup-ai-and-scanners.md) |
| GitHub Actions + report artifact upload | **Supported** | [ci.md](../ci.md), `action.yml` |
| Bitbucket Pipelines script + artifacts | **Supported** | [ci.md](../ci.md) |
| Exit codes for gatekeeping | **Supported** | [ci.md](../ci.md), CLI schema |
| Adaptive fingerprint DB on laptop | **Phase 5** | Local disk under `.repolens/` |
| Jenkins / CircleCI first-class docs | **Not yet** | This document (Phase 7) |
| Email / Slack / Teams notification | **Not yet** | Phase 7 |
| Hosted RepoLens dashboard | **Non-goal for now** | Use artifacts + your own portal |

**Honesty:** LLM review is a due-diligence layer, not a complete production security program ([faq.md](../faq.md)).

## 3. Deployment shapes

### 3.1 Local / corporate laptop (Phase 5 world)

- Checkout on **local disk**  
- Optional Ollama or BYOK cloud key  
- Adaptive SQLite + optional FTS under `.repolens/`  
- Reports under `reports/` (or `--out`)  
- Human reads Markdown; optional `repolens export --pdf` if pandoc present  

### 3.2 Ephemeral CI agent (recommended corporate default)

```
checkout → install RepoLens → (optional) plugins install
  → repolens review|sentinel (scanners-only or auto+secret)
  → upload reports/** as build artifact
  → optional: notify / open ticket / publish to dashboard
```

| Concern | Guidance |
|---------|----------|
| Adaptive cache | **Usually off or cold** on clean agents (`[adaptive] enabled = false` or wipe `.repolens`). Or restore/save `.repolens/repolens.sqlite` via CI cache keyed by repo+branch if you want warm packs. |
| Secrets | CI secret store only (`OPENAI_API_KEY`, etc.). Never commit keys. |
| Network repo mounts | Still **deferred** (Phase 5 §8); CI should use a normal git checkout on agent disk. |
| Fail build | `--fail-on HIGH` (or Action `fail-on`) |

### 3.3 Long-lived CI server / shared agent

Same as 3.2, but `.repolens/` may persist between jobs — document cleanup policy and that fingerprint DBs must not be shared across unrelated repos on the same workspace.

## 4. Report delivery (Phase 7 deliverables)

Reports today: Markdown + optional JSON under `--out` / `reports/`.

| Channel | Approach (planned) | Notes |
|---------|-------------------|--------|
| **CI artifact** | Already: `actions/upload-artifact`, Bitbucket `artifacts:` | Baseline for all forges |
| **Jenkins** | Archive `reports/**`; optional email-ext / HTML publisher | Document freestyle + Pipeline snippet |
| **CircleCI** | `store_artifacts`; orb or raw `pip install` job | Document config.yml example |
| **GitLab CI** | `artifacts: paths: [reports/]` | Document `.gitlab-ci.yml` |
| **Email** | Post-step script or forge plugin; attach `gate_review_report_*.md` | No RepoLens SMTP server — use corporate relay |
| **Slack / Teams** | Webhook with summary + link to artifact | Keep payload free of secrets/code dumps |
| **Dashboard** | Ingest JSON (`--format json\|both`) into existing tool (DefectDojo, custom) | RepoLens does **not** ship a hosted UI in Phase 7 MVP |

### 4.1 Suggested JSON contract for dashboards

Reuse existing report JSON schema (`FindingReport`). Phase 7 may add a thin `repolens ci publish` helper later (optional) that POSTs summary counts to a webhook — not required for MVP if artifacts + scripts suffice.

## 5. Example sketches (to implement in docs/ci.md later)

### Jenkins (Pipeline)

```groovy
pipeline {
  agent any
  environment {
    OPENAI_API_KEY = credentials('openai-api-key') // optional
  }
  stages {
    stage('RepoLens') {
      steps {
        sh '''
          python3 -m venv .venv && . .venv/bin/activate
          pip install "repolens[scanners]"
          repolens plugins install all --yes || true
          repolens review --path . --out ./reports --format both \\
            --fail-on HIGH --scanners-only
          # or full LLM when key present
        '''
        archiveArtifacts artifacts: 'reports/**', fingerprint: true
      }
    }
  }
  // post { always { emailext attachmentsPattern: 'reports/*.md', ... } }
}
```

### CircleCI

```yaml
version: 2.1
jobs:
  repolens:
    docker: [{ image: "cimg/python:3.12" }]
    steps:
      - checkout
      - run: pip install "repolens[scanners]"
      - run: repolens plugins install all --yes || true
      - run: repolens review --path . --out ./reports --format both --fail-on HIGH --scanners-only
      - store_artifacts: { path: reports }
```

## 6. Security & compliance notes (corporate)

- Treat report Markdown/JSON as **internal** — may contain path names and code excerpts.  
- Prefer `--scanners-only` in CI when policy forbids sending code to cloud LLMs; use Ollama on a private runner for LLM in CI if required.  
- Do not enable content FTS learning (`repolens learn`) on shared CI disks without a retention policy.  
- Adaptive fingerprints (paths/hashes only) are lower risk than FTS content but still workspace-local.

## 7. Non-goals (Phase 7 MVP)

- RepoLens-hosted multi-tenant SaaS dashboard  
- Replacing enterprise GRC platforms  
- Guaranteed email delivery without customer SMTP  
- Network filesystem as primary CI workspace (see Phase 5 local-first)

## 8. Exit criteria

- [ ] Documented Jenkins + CircleCI (+ GitLab) examples in [ci.md](../ci.md)  
- [ ] Documented artifact → email / webhook patterns  
- [ ] Guidance: adaptive cache on / off / CI cache restore  
- [ ] Optional: webhook summary helper or dashboard ingest recipe  
- [ ] FAQ “Corporate CI/CD” pointing here  

## 9. Related

- [ci.md](../ci.md) — what ships today  
- [phase-4-ci-and-ecosystem.md](./phase-4-ci-and-ecosystem.md)  
- [phase-5-adaptive-cache-and-recommendations.md](./phase-5-adaptive-cache-and-recommendations.md) §8 local-first / network later  
- [faq.md](../faq.md) — production honesty  
