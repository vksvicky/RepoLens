# ADR-01: RepoLens analysis runtime architecture

| Field | Value |
|-------|-------|
| **Status** | **Accepted** (Phase 2 remotes: git-url, GitHub, Bitbucket, Hugging Face) |
| **Date** | 2026-08-04 |
| **Context** | RepoLens must explain—visually and in prose—how a repository is ingested, prioritised (P1→P2→P3), analysed, validated, and reported across local and remote sources without replacing CI scanners. |
| **Decision** | Adopt a **pipeline architecture**: Source → Inventory → Context pack → LLM analyse → Schema validate → Report. Modes (`review`, `sentinel`, `architecture`) select playbooks and priority bands; remotes and scanner plugins are phased add-ons. |
| **CLI language** | Python 3.11+ |
| **Related** | [Diagram legend](_diagram_legend.md) · [CLI & report schema](../design/cli-and-report-schema.md) · [FAQ](../faq.md) · [phases.md](../phases.md) · Playbooks [`security.md`](../../playbooks/security.md) · [`architecture.md`](../../playbooks/architecture.md) |

---

## Document change log

| Date | Summary | Commit |
|------|---------|--------|
| 2026-08-04 | Initial ADR with HLD, sequence, component, and security-zone diagrams | pending |

---

## 0. How to read these diagrams

| View | Question it answers |
|------|---------------------|
| **§1 HLD** | What are the major building blocks and data artifacts? |
| **§2 Sequence** | What happens on one `repolens review` / `sentinel` run? |
| **§3 Components** | Which application components own which step? |
| **§4 Modes** | How do `sentinel` vs `review` vs `architecture` differ? |
| **§5 Security zones** | Where do tokens and code leave the machine? |
| **§6 Phased growth** | What is Phase 1 vs dashed Phase 2–4? |

Colours and prefixes: [_diagram_legend.md](_diagram_legend.md).

---

## 1. High-level design — analysis runtime

```mermaid
%%{init: {'flowchart': {'htmlLabels': true, 'nodeSpacing': 20, 'rankSpacing': 30}}}%%
flowchart TB
  classDef business fill:#FFF176,stroke:#F57F17,color:#111
  classDef application fill:#90CAF9,stroke:#0D47A1,color:#111
  classDef technology fill:#A5D6A7,stroke:#1B5E20,color:#111
  classDef network fill:#CE93D8,stroke:#4A148C,color:#111
  classDef security fill:#F48FB1,stroke:#880E4F,color:#111
  classDef artifact fill:#EFEBE9,stroke:#5D4037,color:#111
  classDef p1 fill:#EF9A9A,stroke:#B71C1C,color:#111
  classDef p2 fill:#FFCC80,stroke:#E65100,color:#111
  classDef p3 fill:#BBDEFB,stroke:#1565C0,color:#111
  classDef phaseLater fill:#E0E0E0,stroke:#616161,stroke-dasharray: 5 5,color:#111

  subgraph ACTORS["▌ Actors"]
    DEV["«Actor» Developer / auditor"]:::business
    CI["«Actor» CI job"]:::business
  end

  subgraph SOURCES["▌ Sources — Technology"]
    LOCAL["«SysSW» Local path<br/>working tree"]:::technology
    GIT["«SysSW» Git<br/>diff / since-ref"]:::technology
    REMOTE["«T-IF» Remotes<br/>GitHub · Bitbucket · HF · git URL"]:::phaseLater
  end

  subgraph CTRL["▌ RepoLens control plane — Application"]
    CLI["«AppCmp» CLI<br/>typer entrypoint"]:::application
    RES["«AppCmp» SourceResolver"]:::application
    INV["«AppCmp» FileInventory<br/>ignores · size caps · P1 order"]:::application
    PACK["«AppCmp» ContextPacker<br/>playbooks + excerpts"]:::application
    LLM["«AppCmp» LlmClient<br/>structured JSON"]:::application
    VAL["«AppCmp» SchemaValidator<br/>codeExample on Critical/High"]:::security
    RPT["«AppCmp» ReportWriter"]:::application
    PLUG["«AppCmp» ScannerPlugins"]:::phaseLater
  end

  subgraph BANDS["▌ Priority bands"]
    P1["P1 Security<br/>playbooks/security.md"]:::p1
    P2["P2 Bugs / reliability / perf"]:::p2
    P3["P3 Architecture<br/>playbooks/architecture.md"]:::p3
  end

  subgraph EXT["▌ External — Network"]
    MODEL["«T-IF» LLM provider<br/>OpenAI · Anthropic · DeepSeek · Ollama"]:::network
    FORGE["«T-IF» Forge APIs"]:::phaseLater
    SCAN["«SysSW» gitleaks · Semgrep · OSV"]:::phaseLater
  end

  subgraph OUT["▌ Artifacts"]
    MD["«Artifact» gate_review_report_*.md"]:::artifact
    JSON["«Artifact» findings JSON"]:::artifact
    SUM["«Data» confidence % · counts · exit code"]:::artifact
  end

  DEV --> CLI
  CI --> CLI
  CLI --> RES
  LOCAL --> RES
  GIT --> RES
  REMOTE -.-> RES
  FORGE -.-> REMOTE
  RES --> INV
  INV --> PACK
  P1 --> PACK
  P2 --> PACK
  P3 --> PACK
  PACK --> LLM
  LLM --> MODEL
  LLM --> VAL
  PLUG -.-> VAL
  SCAN -.-> PLUG
  VAL --> RPT
  RPT --> MD
  RPT --> JSON
  RPT --> SUM
```

### Layer mapping (ArchiMate-inspired)

| Layer | RepoLens mapping |
|-------|------------------|
| Business | Humans / CI invoking the CLI |
| Application | Resolver → inventory → pack → LLM → validate → report |
| Technology | Git, FS, Python, optional scanners |
| Network | LLM HTTPS; forge APIs (Phase 2) |
| Security | Sentinel mode, schema gate, secret redaction, env-only tokens |
| Artifacts | Playbooks in, Markdown/JSON reports out |

---

## 2. Sequence — one review run

```mermaid
sequenceDiagram
  autonumber
  actor User as «Actor» User / CI
  participant CLI as «AppCmp» CLI
  participant Res as SourceResolver
  participant Inv as FileInventory
  participant Pack as ContextPacker
  participant Llm as LlmClient
  participant Model as LLM provider
  participant Val as SchemaValidator
  participant Rpt as ReportWriter

  User->>CLI: repolens review\|sentinel\|architecture
  CLI->>Res: resolve(--path \| --git-url \| forge)
  Res-->>CLI: worktree root (+ cleanup plan)
  CLI->>Inv: list files (ignores, caps, P1-first)
  Inv-->>CLI: ordered file set / diff hunks
  CLI->>Pack: load playbook(s) + pack excerpts
  Pack-->>CLI: prompt bundle «Artifact»
  CLI->>Llm: analyze(bundle)
  Llm->>Model: HTTPS chat/completions
  Model-->>Llm: JSON issues + summary
  Llm-->>CLI: raw findings
  CLI->>Val: validate schema
  alt Critical/High missing codeExample
    Val->>Llm: one repair re-prompt
    Llm->>Model: repair request
    Model-->>Llm: fixed JSON
  end
  Val-->>CLI: normalized findings + confidence
  CLI->>Rpt: write Markdown (+ JSON)
  Rpt-->>User: report path + exit code
```

**Failure paths:** config/usage → exit `2`; source/auth → `3`; model → `4`; `--fail-on` breached → `1`.

---

## 3. Application components

```mermaid
%%{init: {'flowchart': {'htmlLabels': true}}}%%
flowchart LR
  classDef application fill:#90CAF9,stroke:#0D47A1,color:#111
  classDef security fill:#F48FB1,stroke:#880E4F,color:#111
  classDef artifact fill:#EFEBE9,stroke:#5D4037,color:#111
  classDef technology fill:#A5D6A7,stroke:#1B5E20,color:#111

  CFG["«Artifact» config.toml<br/>+ env secrets"]:::artifact
  PB["«Artifact» playbooks/"]:::artifact

  subgraph CORE["«Collab» Analysis core"]
    CLI["CLI"]:::application
    RES["SourceResolver"]:::application
    INV["FileInventory"]:::application
    PACK["ContextPacker"]:::application
    LLM["LlmClient"]:::application
    VAL["SchemaValidator"]:::security
    RPT["ReportWriter"]:::application
  end

  PY["«SysSW» Python 3.11+"]:::technology
  GIT["«SysSW» Git"]:::technology

  CFG --> CLI
  PB --> PACK
  CLI --> RES --> INV --> PACK --> LLM --> VAL --> RPT
  RES --> GIT
  CLI --> PY
```

| Component | Responsibility |
|-----------|----------------|
| **SourceResolver** | Local path or clone remote to temp; checkout `--ref`; schedule cleanup |
| **FileInventory** | Respect ignore globs; size/binary caps; order security-sensitive paths first |
| **ContextPacker** | Attach mode playbooks; chunk/truncate; never embed API keys |
| **LlmClient** | Provider adapters; temperature/token limits; parse JSON |
| **SchemaValidator** | Enforce finding schema; require `impact` + `codeExample` for Critical/High |
| **ReportWriter** | Markdown (required), JSON (optional); stdout summary via Rich |
| **ScannerPlugins** *(Phase 3)* | Merge deterministic findings into the same report section |

---

## 4. Modes → playbooks → priority bands

```mermaid
%%{init: {'flowchart': {'htmlLabels': true}}}%%
flowchart TB
  classDef application fill:#90CAF9,stroke:#0D47A1,color:#111
  classDef p1 fill:#EF9A9A,stroke:#B71C1C,color:#111
  classDef p2 fill:#FFCC80,stroke:#E65100,color:#111
  classDef p3 fill:#BBDEFB,stroke:#1565C0,color:#111
  classDef security fill:#F48FB1,stroke:#880E4F,color:#111

  S["«AppSvc» repolens sentinel"]:::security
  R["«AppSvc» repolens review"]:::application
  A["«AppSvc» repolens architecture"]:::application
  E["«AppSvc» repolens export"]:::application

  P1["P1 security.md"]:::p1
  P2["P2 reliability pass"]:::p2
  P3["P3 architecture.md"]:::p3
  MD["Existing report.md"]:::application

  S --> P1
  R --> P1
  R --> P2
  R --> P3
  A --> P3
  E --> MD
```

| Mode | Bands | Playbooks | Typical use |
|------|-------|-----------|-------------|
| `sentinel` | P1 only | `security.md` | Fast security guardrail |
| `review` | P1 → P2 → P3 | security + reliability heuristics + architecture (scoped unless `--full-audit`) | Default due diligence |
| `architecture` | P3 (+ scores) | `architecture.md` | Release / milestone audit |
| `export` | — | — | Markdown → PDF/republish |

---

## 5. Security zones & data movement

```mermaid
%%{init: {'flowchart': {'htmlLabels': true}}}%%
flowchart LR
  classDef business fill:#FFF176,stroke:#F57F17,color:#111
  classDef technology fill:#A5D6A7,stroke:#1B5E20,color:#111
  classDef application fill:#90CAF9,stroke:#0D47A1,color:#111
  classDef network fill:#CE93D8,stroke:#4A148C,color:#111
  classDef security fill:#F48FB1,stroke:#880E4F,color:#111
  classDef phaseLater fill:#E0E0E0,stroke:#616161,stroke-dasharray: 5 5,color:#111

  Z0["Z0 Operator<br/>env tokens"]:::business
  Z1["Z1 Worktree<br/>source code"]:::technology
  Z2["Z2 CLI process<br/>redaction"]:::application
  Z3["Z3 LLM API<br/>excerpts + prompts"]:::network
  Z4["Z4 Forge APIs"]:::phaseLater
  Z5["Z5 Scanners"]:::phaseLater

  Z0 -->|config| Z2
  Z1 -->|read files| Z2
  Z2 -->|HTTPS code excerpts| Z3
  Z4 -.->|clone| Z1
  Z5 -.->|SARIF/JSON| Z2
  Z2 -->|reports w/o secrets| Z0
```

| Rule | Detail |
|------|--------|
| Tokens | Env / OS keychain only — never in reports or git |
| Code to LLM | User opts in by running review; document retention with provider |
| Reports | Findings + code examples; strip credential-shaped strings where detected |
| Remotes | Shallow clone to temp; delete after run |

---

## 6. Phased growth (what the grey boxes mean)

| Phase | Adds | Diagram treatment |
|-------|------|-------------------|
| **0** | Playbooks + docs (this ADR) | Baseline |
| **1** | Local `--path`, LLM pipeline, Markdown reports | Solid boxes |
| **2** | `--github` / `--bitbucket` / `--hf` / `--git-url` | Implemented |
| **3** | Optional gitleaks / Semgrep / OSV merge | Dashed until built |
| **4** | GitHub Action, packaging | Out of this runtime diagram |

---

## 7. Consequences

### Positive
- Clear mental model for contributors and adopters  
- Modes map cleanly to playbooks already in-repo  
- Schema gate protects “Critical without a fix example”  
- Same architecture scales from local CLI to CI  

### Trade-offs
- LLM path sends code excerpts off-box (mitigate with local models / Ollama)  
- Context window forces inventory caps and prioritisation (P1-first)  
- Deterministic scanners remain optional complements, not the core  

### Follow-ups
- Implement components in Phase 1 per [cli-and-report-schema.md](../design/cli-and-report-schema.md)  
- Add `docs/adr/exports/` PNG posters if we need icon-heavy slides  
- Future ADR: provider adapter contracts; future ADR: plugin ABI for scanners  

---

## 8. Decision summary

**We will** analyse repositories through a staged pipeline (resolve → inventory → pack → LLM → validate → report), driven by mode-selected playbooks and P1→P2→P3 ordering, with remotes and scanners as explicit later stages—not as a monolithic “scan everything” black box.
