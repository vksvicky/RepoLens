# Phase 9 — Native provider SDKs (design)

**Status:** Design sketch (not implemented)  
**Date:** 2026-08-05  
**Depends on:** Phase 8 (aliases + recipes); streamed wait UX patterns from current LLM layer  
**Not Phase 7 / 8:** Phase 7 = enterprise CI; Phase 8 = OpenAI-compatible aliases + docs. This phase is **Option 3** — first-party adapters where the wire protocol is not OpenAI chat completions.

## 1. Problem

Some high-value hosts cannot be honestly supported as thin `openai_compatible` aliases:

- **Google Gemini / Vertex AI** — distinct generateContent / streaming shapes (unless forced through a third-party OpenAI gateway)  
- **Amazon Bedrock** — SigV4, region, model IDs, invoke vs converse APIs  
- Other proprietary APIs that diverge enough to make alias hacks fragile  

Phase 9 adds **native adapters** only when Phase 8 recipes are insufficient and demand is proven.

## 2. Scope — Option 3

| In scope | Out of scope |
|----------|----------------|
| Native HTTP (prefer `httpx`, avoid heavy SDKs unless necessary) | Replacing Phase 8 aliases that already work |
| Streaming deltas → existing `on_delta` / wait UX | RepoLens-operated multi-tenant proxy |
| `repolens init --provider gemini\|bedrock\|…` | Guaranteeing feature parity with every vendor SDK option |
| Tests with recorded/mocked streams | Bundling vendor credentials |

## 3. Candidate native providers (priority)

| Priority | Provider | Trigger to start | Notes |
|----------|----------|------------------|--------|
| P0 | **Google Gemini** (AI Studio) | Phase 8 OpenAI-compat path inadequate or users insist on native | Stream + JSON mode for FindingReport |
| P0 | **Vertex AI** (Gemini on GCP) | Enterprise GCP customers | ADC / service account; separate from AI Studio key |
| P1 | **Amazon Bedrock** | AWS-standard enterprise ask | Start with Converse API + 1–2 code models |
| P2 | **Other** (Cohere native, etc.) | Explicit customer/requirement | Only after P0/P1 proven |

Phase 8 aliases (Azure, Mistral, Groq, OpenRouter, Together, …) should **remain** OpenAI-compatible — do not rewrite them as native SDKs in Phase 9 without a reason.

## 4. Architecture sketch

```
analyze_raw(prompt, model_cfg, on_delta=…)
  ├─ provider in openai-family / aliases → _analyze_openai_compatible (Phase 8)
  ├─ anthropic → _analyze_anthropic (exists)
  ├─ gemini | vertex → _analyze_gemini (Phase 9)
  └─ bedrock → _analyze_bedrock (Phase 9)
```

Shared contracts:

- Return assistant **text** (JSON FindingReport body)  
- Call `on_delta(chunk)` for wait heartbeats  
- Map timeouts / HTTP errors to `LlmError` with actionable hints  
- Never log API keys or full prompts at info level  

Optional later: pluggable `ProviderAdapter` protocol if the `if provider ==` ladder grows past ~6 branches.

## 5. Security & compliance

- Keys only via env / CI secrets (`GEMINI_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, AWS env/role)  
- Project `.repolens.toml` still cannot override `provider` / `base_url` / `api_key_env` without `--trust-project-config`  
- Document data residency: Vertex/Bedrock region choice is customer-controlled  

## 6. Non-goals (Phase 9 MVP)

- Supporting every Bedrock foundation model on day one  
- Embedding Google/AWS official heavy SDKs if thin `httpx` suffices  
- Changing the FindingReport schema per provider  

## 7. Exit criteria

- [ ] At least one native provider (Gemini **or** Bedrock) ships with stream + init + tests  
- [ ] FAQ/setup mark native vs Phase 8 alias clearly  
- [ ] Fallback guidance: if native unavailable, Phase 8 `openai_compatible` / gateway still documented  
- [ ] No regression to OpenAI / Anthropic / DeepSeek / Ollama paths  

## 8. Related

- [phase-8-provider-aliases-and-recipes.md](./phase-8-provider-aliases-and-recipes.md)  
- [phase-7-enterprise-ci-and-report-delivery.md](./phase-7-enterprise-ci-and-report-delivery.md)  
- [setup-ai-and-scanners.md](../setup-ai-and-scanners.md)  
