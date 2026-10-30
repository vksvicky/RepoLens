# Benchmark one tree, then compare two rows

This is a script in the RepoLens checkout. It is not a `repolens benchmark` command, and it is not installed by `pip install repolens-audit`.

`--arm ci` reviews `tests/fixtures/benchmark/` with scanners and Fast Brain and writes a JSON row whose token totals are zero. That arm does not call a model and does not read an API key.

`--summary` reads two JSON rows and prints one table. It does not start a review. A token from one arm is not converted into a token from the other. A missing count stays `missing`. A ratio whose before value is zero or empty stays `missing`.

`--arm local` requires provider `ollama`. `--arm byok` requires a key provider and refuses `ollama`. The script does not switch models. Those two arms check the provider and then stop. The row writer that would record a model run is still open.

The first documented pair, once that writer lands, is Ollama `qwen2.5-coder:32b` and Anthropic `claude-3-5-sonnet` on this fixture.

## Commands

From the RepoLens checkout:

```bash
./.venv/bin/python scripts/repolens_benchmark.py \
  --path tests/fixtures/benchmark --arm ci --label ci

./.venv/bin/python scripts/repolens_benchmark.py \
  --summary docs/benchmarks/before.json docs/benchmarks/after.json
```

The fixture is ten synthetic Python files. It has no machine path and no network call. Rows are written to `docs/benchmarks/` in the current directory. That folder is gitignored.

## What the table means

| Row | Meaning |
|-----|---------|
| wall seconds | Start to finish. |
| prompt chars | Characters sent to the model. The CI row records zero. |
| prompt tokens | Input tokens the provider reported. |
| completion tokens | Output tokens the provider reported. |
| total tokens | Prompt plus completion. |
| tokens / 1000 prompt chars | How dense that provider's tokenizer was. The cell names the source (`ollama`, `anthropic`, or `none`). |
| scanner seconds | Time the scanners spent running. |
| Fast Brain seconds | Time for the local file checks. |

The CI row records zero tokens because no model was called. That zero is a real measurement.
