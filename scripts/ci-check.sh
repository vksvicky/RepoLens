#!/usr/bin/env bash
# Mirror .github/workflows/ci.yml Python job locally before push/tag.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -x .venv/bin/python ]]; then
  PYTHON=(.venv/bin/python)
  RUFF=(.venv/bin/ruff)
  PYTEST=(.venv/bin/pytest)
else
  PYTHON=(python3)
  RUFF=(ruff)
  PYTEST=(pytest)
fi

echo "==> ruff check src tests"
"${RUFF[@]}" check src tests

echo "==> pytest -q"
"${PYTEST[@]}" -q

echo "CI check OK (matches GitHub Python job)."
unset PYTHON