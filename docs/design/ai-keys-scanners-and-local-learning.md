# Design: AI keys, scanners, OWASP/CVE, and local learning

**Status:** Accepted product principles (Phase 0)  
**Implements:** Phase 1 (keys / local LLM), Phase 3 (scanners), Phase 4+ (local learning)  
**User-facing summary:** [../faq.md](../faq.md)

---

## 1. AI keys — how it works

RepoLens’s **narrative review** (playbooks → structured findings with impact + code examples) is powered by a **large language model**. That model is not trained or hosted by RepoLens itself in v1.

| Path | Needs | Network | Self-sufficient? |
|------|-------|---------|------------------|
| **Cloud LLM** | API key in env / config (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, etc.) | Yes — prompts + code excerpts to provider | No — BYO key |
| **Local LLM** | [Ollama](https://ollama.com) (or compatible OpenAI-style local server) + pulled model | Optional (only to pull models) | **Yes** after model is local |
| **Playbooks only** (no CLI) | Your editor or LLM chat’s AI | Per that product | N/A — you already have access there |
| **Scanners only** (Phase 3 `--scanners-only`) | Plugin binaries | Usually no (except CVE DB updates) | Yes for that slice |

**Principles**

1. **Bring your own key (BYOK)** — RepoLens never ships or embeds a shared API key.  
2. **Keys stay in env / OS secret store** — never written into reports or git.  
3. **Local-first option** — document Ollama (or similar) as a first-class provider so air‑gapped / privacy-sensitive users can run without a cloud key.  
4. **Clear on first run** — if no provider configured, CLI explains the three options (cloud key / local model / scanners-only) and exits with a helpful code.

**Not self-sufficient for full dual review** unless the user supplies **either** a cloud key **or** a local model. Deterministic scanners alone do not produce architecture scores or natural-language remediation with code examples.

---

## 2. Additional libraries — required vs optional vs “built in”

### Phase 1 core (shipped with `pip`/`uv` install)

| Dependency class | Examples (planned) | Bundled? |
|------------------|--------------------|----------|
| CLI / UX | `typer`, `rich` | Yes (Python deps) |
| Config / validation | `pydantic`, `tomllib` | Yes |
| HTTP | `httpx` | Yes |
| Git | system `git` + light Python wrapper | **Git must be on PATH** (not vendored) |
| Playbooks | package data under `playbooks/` | Yes |

### Phase 3 scanners — **not** silently mandatory

| Scanner | Role | How we integrate | Bundle into wheel? |
|---------|------|------------------|--------------------|
| **gitleaks** | Secrets | Subprocess / plugin | **No** by default — `repolens plugins install gitleaks` |
| **Semgrep** | SAST / OWASP-oriented rules | Subprocess | **No** by default — PATH, cache venv, or `repolens[scanners]` |
| **OSV-Scanner** | CVE / dependency vulns | Subprocess | **No** by default — `repolens plugins install osv` |
| **pandoc** | PDF | Subprocess | No — document Print→PDF fallback |

**Decision: detect → use → never hard-fail the LLM path if missing.** (Shipped — see [phase-3-scanners.md](./phase-3-scanners.md).)

```text
repolens review --path .
  → always: LLM path (if provider configured)
  → if scanner on PATH or enabled in config: merge “Automated scanners” section
  → if user asked --require-scanners and missing: exit 2 with install hints
```

**Optional “batteries” extras (Phase 3 — shipped):**

```text
pip install "repolens[scanners]"   # Semgrep via pip; still run plugins install for gitleaks/osv
# or
repolens plugins install gitleaks semgrep osv
```

We **can** build convenience installers; we **should not** force multi‑hundred‑MB native tools into the default `pip install repolens`.

---

## 3. OWASP / CVE / security audit — how scanning actually works

RepoLens uses a **layered** security story. Layers answer different questions.

| Layer | What it covers | Mechanism | Phase |
|-------|----------------|-----------|-------|
| **A. LLM + security playbook** | OWASP-style *classes* of bugs (injection, XSS, broken access control, secrets in code, crypto misuse, …) with explanation + fix examples | `playbooks/security.md` / `sentinel` | 1 |
| **B. Secret scanning** | High-entropy keys, tokens, private keys | gitleaks (etc.) | 3 |
| **C. SAST rules** | Known anti-patterns; many map to OWASP Top 10 / CWE | Semgrep + curated rulesets (incl. OWASP-oriented packs where licensed) | 3 |
| **D. Dependency CVEs** | Known vulnerable package versions (OSV/NVD data) | OSV-Scanner / Grype / ecosystem auditors | 3 |
| **E. Your CI** | Org policy, CodeQL, Snyk, Dependabot | External — report “durability gaps” if absent | always noted |

### Honest limits

- Layer **A** is **not** a CVE database. It will not reliably say “CVE-2024-XXXX in package Y@1.2.3” unless that fact is in the packed context.  
- Layer **D** is the correct tool for **CVE** enumeration.  
- “OWASP compliant” is not a checkbox we stamp; we **map findings to OWASP/CWE categories** in the report when possible and recommend Layers B–D for audit-grade evidence.  
- Playbooks will include an **OWASP Top 10 / ASVS alignment appendix** (documentation), updated over time—not a certification.

### Report sections (target)

1. P1 LLM findings (with OWASP/CWE tags when inferred)  
2. Automated scanners (secrets / SAST / CVE) — only if run  
3. Durability gaps (missing CI scanners, etc.)

---

## 4. Local ML / learning from the user repo

**Goal:** Improve relevance over time **without** uploading the user’s repository to RepoLens servers (there are none in the CLI model).

### What we will do (Phase 4+ — design locked now)

| Feature | Behaviour | Storage |
|---------|-----------|---------|
| **Local index** (optional) | Embeddings / chunk index of the repo for better packing / RAG into the LLM prompt | `.repolens/cache/` or `~/.cache/repolens/<repo-id>/` on **user disk** |
| **Local preference memory** | “User dismissed false positive X”, severity overrides, ignore paths | `.repolens/memory.toml` (project) and/or user config |
| **Informed consent** | First time local learning is enabled, print a clear notice and require `--accept-local-learning` or interactive yes | N/A |
| **No phone-home** | CLI does not send repo contents, embeddings, or memory to a RepoLens backend | — |
| **Cloud LLM still separate** | If the user uses a **cloud** model, excerpts still go to **that provider** per their ToS — local learning does not change that | Disclose in the same notice |

### What we will not do (v1–v3)

- Train a global RepoLens model on customer code  
- Upload embeddings to a central service  
- Silent background learning without notice  
- Claim “fully offline” while a cloud API key is configured  

### Notice copy (required when enabling)

> RepoLens can build a **local** index of this repository to improve future reviews.  
> Data stays on this machine under `.repolens/` (or your configured cache dir).  
> Nothing is uploaded to RepoLens.  
> If you use a **cloud** LLM provider, review prompts may still include code excerpts sent to that provider.  
> Disable anytime: `repolens config set local_learning false` or delete `.repolens/`.

### ML stack (indicative, not locked to a vendor)

- Local embeddings: e.g. `sentence-transformers` or a small ONNX model via optional extra `repolens[local-ml]`  
- Vector store: on-disk (SQLite / Lance / Chroma local)—project decision in Phase 4 ADR  
- Default **off** until user opts in  

---

## 5. Decision summary (plain language)

This section is written for **anyone**—not only engineers. Think of RepoLens as a **careful reviewer you run on a project**, not as a magic box that already contains its own AI brain or a complete security lab.

### 5.1 Do I need an AI key?

**Often yes—but you have choices.**

RepoLens’s main value is explaining problems in plain language and suggesting concrete fixes. That “thinking” comes from an **AI language model**, the same kind of technology behind ChatGPT-style tools.

| Your choice | What you need | Simple analogy |
|-------------|----------------|----------------|
| **Use a cloud AI** (OpenAI, Anthropic, DeepSeek, etc.) | **Your own** API key (like a personal access pass you get from that company) | Hiring an outside specialist—you pay them / use your account; RepoLens just makes the phone call |
| **Use AI on your own computer** (e.g. Ollama) | Install a local model once; **no** cloud API key | The specialist works in your office—nothing is phoned outside for the AI chat |
| **Only run automatic checklist tools** (later feature) | No AI key | A smoke alarm and inventory check—useful, but they don’t write a full consulting report |

**What we will not do:** ship a secret shared AI key inside RepoLens for everyone to use. That would be insecure, expensive, and against most providers’ rules. **You bring your own key**, or you run AI locally.

Your key should live in a password-style setting on your machine—not pasted into reports and not committed to GitHub.

---

### 5.2 Is RepoLens self-sufficient out of the box?

**Not for the full “explain and fix” review—unless you add a local AI.**

Out of the box, RepoLens is like a **well-written review checklist and report template**. To actually perform the smart review, it still needs:

1. **Something that can read and reason about code** → cloud AI key **or** local AI, and  
2. Optionally later, **extra security gadgets** (secret finders, vulnerability lists)—nice to have, not the whole product.

| If you want… | Self-sufficient? | What to set up |
|--------------|------------------|----------------|
| Full written review + fix examples | Only after you add **cloud key** or **local AI** | One of those two |
| Maximum privacy / no cloud AI | **Yes**, after local AI is installed | Local model; keep cloud key unset |
| Only “known vulnerability IDs” and secret leaks | Mostly yes (later plugins) | Install those tools; you won’t get the full narrative report |

**Bottom line:** RepoLens does not pretend to include a free unlimited AI brain. It is open about needing **your** AI setup—and it supports keeping that AI **entirely on your machine** if that matters to you.

**How to set up each option (step-by-step):** see **[../setup-ai-and-scanners.md](../setup-ai-and-scanners.md)**  
— Option A (cloud key), Option B (Ollama / local AI), Option C (scanners only), plus checklists and troubleshooting.

---

### 5.3 Will scanning require lots of extra software? Will you bundle it?

**The basic install stays small. Extra security tools are optional add-ons.**

Imagine buying a notebook that already has good review templates (RepoLens). A full security workshop also uses:

- a **metal detector** for leaked passwords (secret scanner),  
- a **rule book** for common coding mistakes (SAST),  
- a **recall list** for known bad product versions (CVE / dependency check).

Those workshop tools are **large** and change often. So:

- **Default download:** RepoLens + its templates—lightweight.  
- **If the tools are already on your computer:** RepoLens will use them when you ask.  
- **If you want us to help install them:** we can offer an optional “security toolkit” install later—you choose it; it is not forced on everyone.

**We will not** make every user download hundreds of megabytes of scanners just to try a simple review. Missing optional tools will **not** stop the AI review unless you explicitly say “I require those tools.”

---

### 5.4 How do OWASP and CVE security checks work—in everyday terms?

**We use more than one kind of check, because one kind cannot do everything.**

| Kind of check | In plain English | Good for | Not enough alone for |
|---------------|------------------|----------|----------------------|
| **AI review** (`sentinel` / security playbook) | A careful reader looks at *your* code and explains risks (like “this door has no lock”) using ideas from well-known security guides (OWASP-style topics) | Understanding *your* project; clear fix suggestions | A complete list of every known public bug ID in every library |
| **Secret scanner** | Searches for passwords and keys accidentally left in files | Catching leaked credentials | Design/architecture judgment |
| **Pattern scanner (SAST)** | Checks code against a long list of “don’t do this” rules | Repeatable, rule-based issues | Explaining business impact in your words |
| **CVE / dependency check** | Compares your library versions to public “bad version” lists | “Library X version Y has advisory CVE-…” | Reading whether *your* custom code is safe |

**OWASP** here means: we organise and talk about issues using widely taught security themes (injection, broken access control, and so on). It is **guidance alignment**, not a government stamp that says “OWASP certified.”

**CVE** here means: publicly tracked vulnerability IDs for software packages. For those, RepoLens uses **OSV-Scanner** (`--scanners` / `plugins install`), not guesses from the AI alone.

**Honest promise:** AI helps you *understand and fix*. Checklist tools help you *prove and inventory*. Production-ready teams use **both**, plus their normal tests and CI—not RepoLens instead of everything else.

---

### 5.5 Can it learn from my project with ML? Where does that data live?

**Yes, we plan to—but only on your computer, only if you say yes, and we will tell you clearly.**

Over time RepoLens can remember things like:

- folders you always want ignored,  
- alerts you marked as “false alarm,”  
- a local search index so the next review “knows” your project better.

| Promise | Meaning for you |
|---------|-----------------|
| **Local only** | Learning data stays in a folder on **your** machine (for example under `.repolens/`) |
| **Opt-in** | This stays **off** until you turn it on |
| **We tell you** | The first time, you get a short plain-language notice—not fine print buried in a license |
| **No RepoLens cloud training** | We do **not** take your code to train a central RepoLens model |
| **Cloud AI is separate** | If you still use a **cloud** AI key, pieces of code may still be sent to **that** company for the review itself. Local learning does not cancel that. For “nothing leaves my machine,” use **local AI** and keep local learning on your disk |

You can turn learning off or delete the local folder anytime.

---

### 5.6 One-page cheat sheet

| Question | Plain answer |
|----------|--------------|
| Need an AI key? | For cloud AI, **yes (yours)**. For AI on your PC, **no cloud key**. For checklist-only scans later, **no AI key**. |
| Self-sufficient? | **Full report:** only after you add cloud AI **or** local AI. **RepoLens alone** is the process + templates, not a hidden free AI service. |
| Extra scanning tools built-in? | **Optional.** Small default install; big security tools added only if you want them. |
| OWASP / CVE? | **AI** explains OWASP-style risks in your code. **Separate tools** list real CVE IDs in dependencies. We do both layers; we don’t pretend AI replaces CVE databases. |
| Learn from my repo? | **Planned, local, opt-in, announced up front.** No silent upload to RepoLens for training. |

---

## 6. Follow-ups

| Item | Phase |
|------|-------|
| Provider config + first-run key/Ollama UX | 1 |
| OWASP/CWE tags on LLM findings + playbook appendix | 1–2 |
| Plugin ABI + gitleaks/Semgrep/OSV | 3 (shipped) |
| `repolens plugins install` / `[scanners]` extra | 3 (shipped) |
| Local learning ADR + `.repolens/` layout | 4 |
| Privacy section in SECURITY.md | 1 (doc), 4 (implementation) |
