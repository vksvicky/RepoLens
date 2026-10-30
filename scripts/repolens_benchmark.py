#!/usr/bin/env python3
"""One benchmark arm, or a before/after table. Not a ``repolens benchmark`` command.

``--arm ci`` is scanners-only and records zero tokens. It does not read an API key.
``--arm local`` requires Ollama. ``--arm byok`` requires a key provider and refuses
Ollama. Those two arms check the provider, then stop until the row writer lands.
``--summary`` reads two JSON rows and does not start a review.

    ./.venv/bin/python scripts/repolens_benchmark.py \
        --path tests/fixtures/benchmark --arm ci --label ci
    ./.venv/bin/python scripts/repolens_benchmark.py \
        --summary docs/benchmarks/before.json docs/benchmarks/after.json

Rows stay in ``docs/benchmarks/``, which is gitignored.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from repolens.benchmark_cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
