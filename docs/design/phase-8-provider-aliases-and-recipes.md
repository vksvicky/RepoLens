# Phase 8 — Provider aliases & setup recipes (design)

**Status:** Design sketch (not implemented)  
**Date:** 2026-08-05  
**Depends on:** Current BYOK (`openai` / `anthropic` / `deepseek` / `openai_compatible` / `ollama`) + streamed wait UX  
**Not Phase 7:** Enterprise CI stays Phase 7; this phase expands *how users point at more LLM hosts*.

## 1. Problem

Teams ask for Gemini, Azure OpenAI, Mistral, Groq, etc. Today those work only if the user already knows to configure `openai_compatible` + `base_url`. That is easy to get wrong in corporate environments.

Phase 8 makes common hosts **first-class by name** (Option 1) and ships **copy-paste recipes** (Option 2) without taking on native vendor SDKs (that is Phase 9).

## 2. Scope — Option 1 + Option 2

| Option | Deliverable | In Phase 8? |
|--------|-------------|-------------|
| **1 — Named aliases** | `repolens init --provider <alias>` writes correct `provider` / `base_url` / `api_key_env` / default `model` | **Yes** |
| **2 — Docs & recipes** | Setup tables, CI secret examples, FAQ matrix rows | **Yes** |
| **3 — Native SDKs** | Gemini/Vertex, Bedrock, etc. first-party HTTP/SDK adapters | **No → Phase 9** |

Transport in Phase 8 stays:

- OpenAI-compatible chat completions (streamed) for aliases that speak that protocol  
- Existing Anthropic Messages path for `anthropic`  
- Gemini / Bedrock **named** only if we can map them through a compatible gateway **or** document “use Phase 9 / openai_compatible proxy”; do **not** block Phase 8 on native Gemini

## 3. Provider backlog (requirement-driven)

### 3.1 P0 — enterprise / high demand (aliases + recipes)

| Alias | Maps to | Key env (default) | Notes |
|-------|---------|-------------------|--------|
| `azure` / `azure_openai` | OpenAI-compatible | `AZURE_OPENAI_API_KEY` (or `REPOLENS_API_KEY`) | Requires `--base-url` (resource endpoint) + deployment as `model` |
| `mistral` | OpenAI-compatible | `MISTRAL_API_KEY` | `https://api.mistral.ai/v1` |
| `groq` | OpenAI-compatible | `GROQ_API_KEY` | Fast CI-friendly inference |
| `openrouter` | OpenAI-compatible | `OPENROUTER_API_KEY` | Multi-model router; model ids are vendor-specific |

### 3.2 P1 — strong demand (aliases if API is OpenAI-shaped; else recipe → Phase 9)

| Alias / name | Phase 8 treatment | Phase 9 if needed |
|--------------|-------------------|-------------------|
| `gemini` | Recipe: AI Studio / Vertex **OpenAI-compatible endpoint** if available; else “Phase 9 native” | Native Google Generative Language / Vertex |
| `together` | OpenAI-compatible alias | — |
| `fireworks` | OpenAI-compatible alias | — |

### 3.3 P2 — document as `openai_compatible` recipes only (no new enum until asked)

| Host | Recipe focus |
|------|----------------|
| LM Studio | Local `http://127.0.0.1:1234/v1` |
| vLLM / llama.cpp server | Self-hosted OpenAI-compatible |
| Cloudflare Workers AI | Gateway URL + key |
| Hugging Face Inference (OpenAI-compatible routers) | When endpoint speaks chat completions |
| Cohere / Perplexity | Only if they expose OpenAI-compatible chat; else Phase 9 / defer |

### 3.4 Explicitly deferred to Phase 9

| Provider | Reason |
|----------|--------|
| Google Gemini / Vertex (native) | Non–OpenAI request/response shapes |
| Amazon Bedrock (native) | AWS SigV4 + model-specific bodies |
| Other proprietary SDKs | Cost/complexity; ship only with clear demand |

## 4. Design approach (aliases)

```
repolens init --provider groq --model llama-3.3-70b-versatile --force
  → writes provider = "openai_compatible"   # or keep alias string + normalize at load
       base_url = "https://api.groq.com/openai/v1"
       api_key_env = "GROQ_API_KEY"
       model = "…"
```

**Recommendation:** Store either:

- **A (preferred for MVP):** `provider = "openai_compatible"` plus documented alias metadata in init only, **or**
- **B:** Allow alias strings in `ProviderName` that normalize to the same transport in `llm.py` (`groq` → openai-compatible client).

B is nicer UX (`provider = "groq"` in config). Phase 8 should pick **B** if the Literal union stays maintainable; otherwise A + recipes.

Streaming wait UX: reuse existing OpenAI-compatible SSE path — no new progress code per alias.

## 5. Docs deliverables

- Expand [setup-ai-and-scanners.md](../setup-ai-and-scanners.md) alias table  
- FAQ “Which providers?” → Phase 8/9 rows  
- CI examples: Jenkins/GHA secrets for `AZURE_OPENAI_API_KEY`, `GROQ_API_KEY`, etc. (coordinate with Phase 7 docs, do not block Phase 7)  
- `.repolens.example.toml` comments for aliases  

## 6. Non-goals (Phase 8)

- Native Gemini / Bedrock / Vertex SDKs (Phase 9)  
- RepoLens-hosted proxy or shared keys  
- Guaranteeing every third-party OpenAI “compatible” host behaves identically (document quirks)  

## 7. Exit criteria

- [ ] `repolens init` accepts P0 aliases (Azure, Mistral, Groq, OpenRouter) with correct defaults  
- [ ] Setup + FAQ list P0–P2 with “alias vs recipe vs Phase 9”  
- [ ] At least one integration test or unit test per alias default map  
- [ ] Gemini called out: OpenAI-compatible recipe **or** Phase 9 — no half-native adapter  

## 8. Related

- [phase-7-enterprise-ci-and-report-delivery.md](./phase-7-enterprise-ci-and-report-delivery.md) — CI/delivery only  
- [phase-9-native-provider-sdks.md](./phase-9-native-provider-sdks.md) — Option 3  
- [ai-keys-scanners-and-local-learning.md](./ai-keys-scanners-and-local-learning.md) — BYOK principles  
