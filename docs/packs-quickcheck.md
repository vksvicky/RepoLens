# Domain packs — quick check

Short expected-output guide for Phase 6.10 packs.  
**All commands (install → review → after-report → troubleshooting):** [command-atlas.md](./command-atlas.md)  
Full pack detail: [packs.md](./packs.md).

## Commands → what you should see

| Command | Expect |
|---------|--------|
| `repolens packs list` | Table with `azure-sentinel`; tip about `--pack` / `[packs] enabled` |
| `repolens review --path . --pack azure-sentinel --scanners-only` | Scanners run; summary may show **0** findings on a non-SOAR repo (normal) |
| Same as above **with `-v`** | Extra line: `Domain packs: azure-sentinel (N heuristic finding(s))` |
| `repolens review --path . --scanners-only -v` *(no `--pack`)* | **No** `Domain packs:` line (packs off by default) |

## If you see this → it means

| Observation | Meaning | Next step |
|-------------|---------|-----------|
| `Domain packs: azure-sentinel (0 heuristic finding(s))` | Pack is on; no tenant/secret smells in matching files | OK for RepoLens itself and most app repos |
| `Domain packs: azure-sentinel (N…)` with N ≥ 1 | Heuristics found GUID/secret patterns | Open the Markdown/JSON report; category `pack.azure_sentinel` |
| Summary Critical/High/Medium all 0 with pack on | Clean scanners **and** no pack hits | Expected on this codebase |
| No `Domain packs:` line and you passed `--pack` | Likely not using `-v` (detail is verbose-only) | Re-run with `-v` |
| `repolens packs list` missing / unknown command | Old install without Phase 6.10 | `pip install -e ".[dev]"` from the RepoLens clone |
| Core `repolens sentinel` without `--pack` | Unchanged P1 playbook only | Correct — pack is opt-in |

## Smoke test that *should* find something

```bash
mkdir -p /tmp/soar-smoke && cat > /tmp/soar-smoke/workflow.json <<'EOF'
{"tenantId": "11111111-1111-1111-1111-111111111111"}
EOF
repolens review --path /tmp/soar-smoke --pack azure-sentinel --scanners off --scanners-only -v
```

Expect: `Domain packs: azure-sentinel (1 heuristic finding(s))` and a Medium finding about a hardcoded tenant ID.

## Approximate duration (general idea only)

Times vary with disk, antivirus, cold Semgrep cache, and whether OSV/Trivy hit the network. Figures below are **order-of-magnitude** for a ~200-file Python repo (RepoLens-sized) with default scanners (`gitleaks`, `semgrep`, `osv`) and **no LLM**.

| Machine class (examples) | `--scanners-only` + `--pack` | Notes |
|--------------------------|------------------------------|--------|
| Apple Silicon laptop (M1/M2/M3, SSD) | ~1–5 s | Dogfood on RepoLens often ~1 s warm |
| Mid Windows / Linux laptop (8+ cores, SSD) | ~2–15 s | First Semgrep run often slower |
| Small CI runner (2 vCPU) | ~10–45 s | Cold caches + network for OSV |
| Large monorepo (thousands of files) | tens of seconds → a few minutes | Dominated by Semgrep/OSV, not the pack |

**Pack overhead:** usually under a second on small/medium trees (light text scan of JSON/YAML/Bicep-ish files).

**With LLM** (full deep + local Ollama): expect **hours**, not minutes — dogfood on M4 Pro / 128 GB is often **≥1 h for ~200 files** and **~2–3+ h for ~800 files**. Cloud APIs are still multi-pass / token-bound. Prefer `--ci` (bypass when scanners clean) or `--scanners-only` for fast loops.

Full matrix: [command-atlas.md § Approximate duration](./command-atlas.md#7-approximate-duration).
