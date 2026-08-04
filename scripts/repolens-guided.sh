#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${ROOT}/repolens_guided.py"
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$PY" "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$PY" "$@"
else
  echo "python3/python not found" >&2
  exit 127
fi
