# Phase 7: Enterprise CI/CD & Report Delivery — Execution Checklist

**Status:** Docs MVP implemented (2026-09-06) — close [#3](https://github.com/vksvicky/RepoLens/issues/3) when PR merges  
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
- [x] **Jenkins Pipeline (`Jenkinsfile`):** Declarative snippet + `archiveArtifacts` + exit-code gatekeeping
- [x] **CircleCI (`.circleci/config.yml`):** `cimg/python:3.12` + `store_artifacts`
- [x] **GitLab CI (`.gitlab-ci.yml`):** `artifacts: when: always`
- [x] **Azure DevOps Pipeline (`azure-pipelines.yml`) [Nice-to-have / Stretch]:** Sketch only

### B. Report Delivery & Notifications
- [x] **Artifact Packaging & Delivery:** MD / JSON / SARIF / SBOM table in ci.md
- [x] **Email Notification Recipe:** Corporate SMTP / Jenkins emailext (no RepoLens SMTP)
- [x] **Slack / Teams Webhook Recipe:** Summary counts + artifact URL only
- [x] **External Dashboard Ingestion Contract:** FindingReport JSON / SARIF → DefectDojo / custom

### C. Operational & Compliance Guidance
- [x] **Ephemeral CI Cache Guidance:** `[adaptive] enabled = false` default; optional branch-keyed SQLite
- [x] **Forge-side Push-Protection Clarification:** Pre-receive vs post-land audit
- [x] **Corporate CI/CD FAQ (`docs/faq.md`):** Section *Corporate CI/CD & delivery (Phase 7)*

---

## 3. Exit Criteria

1. [x] `docs/ci.md` contains verified snippets for Jenkins, CircleCI, and GitLab CI.
2. [x] Webhook and email notification patterns are clearly documented with security guardrails.
3. [x] Adaptive cache policy for ephemeral vs persistent runners is documented.
4. [x] Forge push-protection vs audit boundaries are articulated in `docs/faq.md`.
5. [ ] Issue #3 closed upon merge of the Phase 7 docs PR.
