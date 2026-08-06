# Optional domain packs (Phase 6.10)

Domain packs add niche playbook guidance and light deterministic heuristics for
workflows where generic AST SAST is weak. **They are off by default** and never
replace Checkov, ARM-TTK, or your cloud policy tools.

**All CLI commands (holy grail):** [command-atlas.md](./command-atlas.md)  
**Pack-only quick check:** [packs-quickcheck.md](./packs-quickcheck.md)

## List packs

```bash
repolens packs list
```

Today:

| Id | Focus |
|----|--------|
| `azure-sentinel` | Microsoft Sentinel analytics, Logic Apps, SOAR workflows |

## Enable a pack

**CLI** (repeatable):

```bash
repolens review --path . --pack azure-sentinel --scanners-only
repolens sentinel --path . --pack azure-sentinel --ci --fail-on HIGH
```

**Config** (user or project `.repolens.toml`):

```toml
[packs]
enabled = ["azure-sentinel"]
```

CLI `--pack` merges with config (deduped). Unknown ids are ignored.

## What `azure-sentinel` does

1. **Playbook** — appended to LLM prompts (deep and single-shot) when the pack is on
2. **Heuristics** — scans JSON/YAML/Bicep/ARM-ish files for:
   - hardcoded tenant / subscription GUIDs
   - embedded connector secrets (`clientSecret`, shared keys, …)

Findings use category `pack.azure_sentinel` and `source=heuristic`. They run even
with `--scanners-only` or CI triage LLM-bypass, so SOAR repos get signal without an
LLM call.

## What it does *not* do

- Change core `repolens sentinel` when the pack is **off**
- Replace Checkov / ARM-TTK / Azure Policy
- Pivot RepoLens into an Azure-only product

## Future packs

Mobile and other niches can register the same way under `repolens.packs`. See the
umbrella design §6.10.
