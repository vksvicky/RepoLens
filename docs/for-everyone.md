# RepoLens in plain language

This page is for someone who will **read a review**, not install the tool. A founder, a buyer, an auditor, or a manager can stop here. The person who runs the commands starts at [which-command.md](./which-command.md).

## What it is

RepoLens reviews a software project and writes a report. The report covers three questions:

1. **Security** — could someone break in, steal data, or find a leaked password?
2. **Reliability** — is the project likely to fail in ordinary use?
3. **Architecture** — is the project shaped so a team can keep changing it safely?

It runs on a computer you choose. There is no RepoLens website to log into, and RepoLens does not keep a copy of the project.

## What you receive

| You ask for | You get |
|-------------|---------|
| A review | A written report you can open, share, or print |
| A board summary | Two short pages: traffic lights, the serious items, and a note on what the score means |
| An evidence pack | A zip of the report plus the supporting files, for a data room |

A sample report is here: [sample audit report](../reports/samples/sample_audit_report.md).

## How to read the score

The number on the report says **how complete this review was**. A high number means the checklist for this run was answered. It does not mean the project is safe, and it does not mean a person or a model read every file.

Read the three traffic lights first: security, reliability, architecture. Then read items marked **Critical** or **High**. Those are the ones to discuss. Medium and Low can wait.

The report also says how much of the project each kind of check looked at:

- The automatic checkers can walk the **whole** project.
- The written explanation looks at a **chosen set** of files, usually up to 200, and the report says how many.

## What the automatic checks are looking for

| Check | In everyday words |
|-------|-------------------|
| Secret search | Passwords and keys left in the project |
| Pattern check | Common “do not do this” mistakes in the code |
| Known-bug list | Libraries whose published version has a known flaw |
| Container and server check | Problems in the files that describe how the software is packaged and run |
| Infrastructure check | Problems in files that describe servers and cloud setup. This one stays off until someone turns it on |

These checks use **fixed versions**. When RepoLens installs them, it also checks every extra piece those tools need, so a different file cannot be swapped in quietly. That install is built for **Python 3.12**. The downloadable container already includes the pattern check for that version. If an install stops and names a different Python, hand that message to the person who runs the tool. It means the version does not match, not that a download was damaged.

## If one change might affect other files

A review of “what just changed” records how many files were in that change, and which neighbouring files are directly connected. A review of the whole project says there was no limited change to measure. Either way the report answers the question, instead of leaving a blank.

Ask for this when a fix is about to touch a busy part of the project: “What else is next to this file?”

## What to hand the person who runs it

You do not need to learn the commands. Forward one of these lines.

| You want | They run |
|----------|----------|
| A fast check before a change is merged | `repolens review --preset pr --path . --ci --fail-on HIGH` |
| A review of what just changed | `repolens which changed` |
| A full due-diligence review | `repolens which audit` |

`repolens which pr` prints the fast check and does not itself decide that a failure should stop the merge. The first line above is the one that does.

After it finishes, ask them for the board summary:

```bash
repolens export --executive-summary --out reports
```

## What this review is not

- It is not a certificate. A fintech or health note in a report is a hint to verify, not a PCI or HIPAA stamp.
- It is not a replacement for the company’s existing security tools, tests, or release process.
- It does not change the project by itself. A suggested fix for one item is a separate step, and a person still has to apply it.
- It does not include a shared AI account. A full written explanation needs the team’s own cloud AI access, or an AI running on their own computer. The fast check above does not need that.

## Where to go next

| If you want… | Open |
|--------------|------|
| Which command to run | [which-command.md](./which-command.md) |
| How to set up cloud AI, a local AI, or checkers only | [setup-ai-and-scanners.md](./setup-ai-and-scanners.md) |
| The longer answers, still in plain words | [faq.md](./faq.md) |
