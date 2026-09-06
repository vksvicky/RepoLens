# Phase 7: Enterprise CI/CD & Report Delivery — Execution Checklist

**Status:** Ready to execute after Wave A (A1 #14 + A2 #17 MVP)  
**Date:** 2026-09-06  
**Issue:** [#3](https://github.com/vksvicky/RepoLens/issues/3)  
**Parent Roadmap:** [docs/phases.md](../phases.md#phase-7--enterprise-cicd--report-delivery-design)  
**Design Reference:** [docs/design/phase-7-enterprise-ci-and-report-delivery.md](./phase-7-enterprise-ci-and-report-delivery.md)  
**Parallel Track:** [#1](https://github.com/vksvicky/RepoLens/issues/1) (PyPI Alpha: Trusted Publisher + local dogfood + tag; TestPyPI optional)

---

## 1. Context & Goal

Provide production-minded corporate CI/CD integration and delivery recipes without building a RepoLens SaaS platform:
- Running on corporate CI runners (Jenkins, CircleCI, GitLab CI).
- Delivering Markdown, JSON, SARIF, and SBOM artifacts to artifact stores, email relays, and chat webhooks.
- Clarifying cache behavior on ephemeral runners and distinguishing forge secret push-protection from RepoLens post-commit audit.

---

## 2. Thin Execution Checklist

### A. CI Forge Integrations (docs/ci.md)
- [ ] **Jenkins Pipeline (`Jenkinsfile`):**
  - Declarative pipeline snippet with virtual environment setup and `pip install "repolens[scanners]"`.
  - Step running `repolens review` or `repolens sentinel` with `--fail-on HIGH`.
  - Artifact archiving via `archiveArtifacts artifacts: 'reports/**', fingerprint: true`.
  - Exit code handling for build gatekeeping.
- [ ] **CircleCI (`.circleci/config.yml`):**
  - Dedicated job snippet using `cimg/python:3.12`.
  - Scanner plugin setup (`repolens plugins install all --yes || true`).
  - Storing review reports via `store_artifacts: { path: reports }`.
- [ ] **GitLab CI (`.gitlab-ci.yml`):**
  - Job definition with `python:3.12-slim` image.
  - Review execution with report output to `reports/`.
  - Artifact preservation via `artifacts: paths: [reports/]`, `when: always`.
- [ ] **Azure DevOps Pipeline (`azure-pipelines.yml`) [Nice-to-have / Stretch]:**
  - Example snippet for Azure Pipelines publishing build artifacts (`PublishBuildArtifacts@1`).
  - Note: Stretch goal, not a Wave B blocking exit criterion.

### B. Report Delivery & Notifications
- [ ] **Artifact Packaging & Delivery:**
  - Document archiving of all report artifacts: Markdown summary, JSON report, anchored SARIF (`--sarif`), and CycloneDX SBOM (`sbom.cdx.json`).
- [ ] **Email Notification Recipe:**
  - Document post-step corporate SMTP relay pattern attaching `reports/gate_review_report_*.md`.
  - Clarify that RepoLens does not operate an SMTP server.
- [ ] **Slack / Teams Webhook Recipe:**
  - Provide a lightweight `curl` / Python script snippet posting a formatted JSON summary payload to a webhook.
  - Security guardrail: explicitly enforce that payloads contain only high-level summary counts and artifact links, never raw code excerpts or secrets.
- [ ] **External Dashboard Ingestion Contract:**
  - Document the JSON schema contract (`FindingReport`) for ingestion into external tools (DefectDojo, custom internal security portals).
  - Explicit non-goal: RepoLens does not ship a hosted SaaS dashboard.

### C. Operational & Compliance Guidance
- [ ] **Ephemeral CI Cache Guidance:**
  - Document runner cache recommendations:
    - Default recommendation: `[adaptive] enabled = false` on clean/ephemeral runners.
    - Warm cache alternative: restore and save `.repolens/repolens.sqlite` via CI cache keying on repo and branch.
    - Explicit warning: never persist SQLite/FTS caches across unrelated repositories on shared multi-tenant runners.
- [ ] **Forge-side Push-Protection Clarification:**
  - Document the operational boundary between native forge secret push protection (GitHub secret scanning push protection, GitLab push rules) and RepoLens.
  - Emphasize that native forge push-protection blocks pre-receive commits, whereas RepoLens serves as an in-depth audit of landed/staged code in PR review pipelines.
- [ ] **Corporate CI/CD FAQ (`docs/faq.md`):**
  - Add "Corporate CI/CD & Delivery" FAQ section covering runner setup, secret handling, and cache configuration.

---

## 3. Exit Criteria

1. `docs/ci.md` contains verified snippets for Jenkins, CircleCI, and GitLab CI.
2. Webhook and email notification patterns are clearly documented with security guardrails.
3. Adaptive cache policy for ephemeral vs persistent runners is documented.
4. Forge push-protection vs audit boundaries are articulated in `docs/faq.md`.
5. Issue #3 is closed upon completion.
