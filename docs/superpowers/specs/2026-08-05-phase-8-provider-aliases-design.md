# Phase 8 — Provider aliases & recipes (spec)

**Date:** 2026-08-05  
**Status:** Design approved for backlog (not implemented)  
**Parent design:** [phase-8-provider-aliases-and-recipes.md](../../design/phase-8-provider-aliases-and-recipes.md)

## Decision

Phase **8** = Option **1** (named `init` aliases) + Option **2** (docs/recipes).  
Phase **9** = Option **3** (native SDKs).  
Phase **7** remains enterprise CI/CD only — no provider expansion there.

## MVP aliases (P0)

`azure` / `azure_openai`, `mistral`, `groq`, `openrouter` → OpenAI-compatible transport + streamed wait UX.

## Deferred

Native Gemini / Vertex / Bedrock → Phase 9.  
LM Studio / vLLM → Phase 8 recipes under `openai_compatible` only.
