# Using RepoLens playbooks without the CLI

Prefer the CLI when you can (`pip install -e .` from a clone — see [setup-ai-and-scanners.md](./setup-ai-and-scanners.md)). You can also run the same reviews with **ChatGPT**, **Claude**, **GitHub Copilot Chat**, or any LLM that can read your repository.

For choosing and preparing **cloud AI vs local AI vs scanners**, see the step-by-step guide: [setup-ai-and-scanners.md](./setup-ai-and-scanners.md).

## 1. Open the project you want to review

Open the **target repository** (local checkout) in your editor or chat tool—not only this RepoLens docs repo.

## 2. Attach or paste a playbook

| Goal | Playbook |
|------|----------|
| Security-only (`repolens sentinel`) | [playbooks/security.md](../playbooks/security.md) |
| Full architecture / production audit | [playbooks/architecture.md](../playbooks/architecture.md) |
| Full dual review (`repolens review`) | Use **both**, in order: security first, then architecture (scoped to the change unless you want a full audit) |

## 3. Example prompts

**Security-only (`sentinel` style):**
```text
Follow playbooks/security.md against this repository.
Report Critical/High/Medium/Low with file:line, impact, recommended fix,
and a code example for every Critical and High finding.
Give a confidence % and a prioritized fix plan.
Do not commit or push.
```

**Full review (`review` style):**
```text
Run a P1 → P2 → P3 dual review:
1) playbooks/security.md
2) bugs/reliability/performance on the change blast radius
3) playbooks/architecture.md (scoped, or full if I say "full audit")
Require impact + codeExample on Critical/High.
End with confidence %, fix plan, and durability gaps (tests, CI, scanners).
Do not commit or push.
```

**Export a report:**
```text
Save the review as docs/reviews/gate_review_report_YYYY-MM-DD.md
including all findings and code examples.
```

## 4. Viewing and exporting reports

- **View:** Chat output, or open the saved `.md` file in any Markdown preview.
- **Export Markdown:** Ask your LLM tool to write `gate_review_report_YYYY-MM-DD.md`.
- **PDF:** `pandoc report.md -o report.pdf` or Print → Save as PDF.

## 5. When the CLI arrives

The same playbooks will be loaded automatically by:

```bash
repolens sentinel --path .
repolens review --path .
```

See [phases.md](./phases.md) for progress.
