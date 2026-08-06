# Rules — what RepoLens checks (and why)

Plain guide for anyone who runs reviews. No need to read the design docs.

## In one sentence

**Rules** are the checklists RepoLens follows when it reviews your code: security first, then reliability, then architecture. You can leave the defaults on, or turn pieces off for your project.

## Why rules exist

| Reason | What it means for you |
|--------|------------------------|
| Consistency | The same kinds of issues are looked for every time |
| Clarity | Findings map to a named checklist (not random AI vibes) |
| Control | You can disable a rule for a project without forking RepoLens |
| Honesty | Optional “calibrations” reduce known AI false alarms |

Rules are **guidance for the review**. They do **not** replace tests, Semgrep, CodeQL, or Dependabot.

## The three built-in rules

| Rule | When it runs | What it’s for |
|------|--------------|---------------|
| **security** | Always in `review` and `sentinel` | Secrets, injection, auth, unsafe patterns |
| **reliability** | Full `review` | Bugs, error handling, performance risks |
| **architecture** | Full `review` / `architecture` | Structure, maintainability, production readiness |

The full text of each checklist lives in [playbooks/](../playbooks/) (and the packaged copies under `src/repolens/rules/defaults/`).  
Using playbooks in ChatGPT/Claude without the CLI: [using-playbooks.md](./using-playbooks.md).

## How RepoLens picks which rules to use

1. **Packaged defaults** (shipped with RepoLens) — all three on  
2. **Your user config** (optional overrides)  
3. **This project** (`.repolens/` in the repo you review) — wins if both exist  

So: project settings beat personal settings beat defaults.

## Turn a rule on or off (project)

In the project you are reviewing, create `.repolens/rules.json`:

```json
{
  "rules": {
    "architecture": { "enabled": false }
  }
}
```

That example skips the architecture checklist for this project only. Security and reliability stay on.

To replace the *wording* of a rule for one project, put a Markdown file at:

```text
.repolens/rules/security.md
```

(same idea for `reliability.md` / `architecture.md`). Prefer small edits; keep Critical/High findings requiring a clear fix example.

## Related switches (not the same as rules)

These live in config (see [`.repolens.example.toml`](../.repolens.example.toml)):

| Setting | What it does | Why |
|---------|--------------|-----|
| `[deep]` | Multi-pass deep review (default on) | Better coverage on large repos |
| `[deep].fp_calibrations` | Softens known AI false positives (e.g. safe `subprocess` list calls) | Less noise without hiding real `shell=True` issues |
| `[explain]` | `repolens explain <id>` deep-dives | Extra detail on one finding when you need it |

Disable an FP calibration only if you want the raw AI severity back:

```toml
[deep]
fp_calibrations = { subprocess_list_not_injection = false }
```

## Deep-dive one finding

Reports show a **Run ID** and **Stable ID** on each issue. To open a fuller write-up:

```bash
repolens explain <uuid> --path . --out ./reports
```

Details: [FAQ — explain](./faq.md#how-do-i-deep-dive-one-finding-phase-6-explain).

## What not to expect

- A complete CVE list for every library (use OSV / your SCA tools)  
- Zero false positives from AI alone  
- Rules that change your app’s code for you  

## See also

- [try-on-your-repo.md](./try-on-your-repo.md) — run a review  
- [faq.md](./faq.md) — metrics, scanners, dogfood noise  
- [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) — model + scanners setup  
