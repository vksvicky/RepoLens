#!/usr/bin/env bash
# Full combined review: scanners, clean code, and the whole-tree model write-up.
#
#   ./scripts/selfdog-review.sh
#   TARGET=/path/to/other/tree ./scripts/selfdog-review.sh
#   ./scripts/selfdog-review.sh --dry-run
#
# Reviews this checkout. When TARGET is set, reviews that tree instead and
# still writes the report under reports/selfdog-deep in this checkout.
# The dev install may point at another checkout. PYTHONPATH keeps this
# checkout's src first. Often an hour or more on local qwen2.5-coder:32b.
# Extra flags are added at the end. --timeout 7200 is the longest one model
# pass may run.
set -euo pipefail
cd "$(dirname "$0")/.."

review_path="${TARGET:-.}"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ -x .venv/bin/repolens ]]; then
  REPOLENS=(.venv/bin/repolens)
else
  common="$(cd "$(git rev-parse --git-common-dir)" && pwd)"
  shared="$(cd "$common/.." && pwd)/.venv/bin/repolens"
  if [[ -x "$shared" ]]; then
    REPOLENS=("$shared")
  else
    REPOLENS=(repolens)
  fi
fi

exec "${REPOLENS[@]}" review \
  --path "$review_path" \
  --out reports/selfdog-deep \
  --full \
  --full-audit \
  --deep \
  --scanners gitleaks,semgrep,osv,trivy,checkov \
  --model qwen2.5-coder:32b \
  --timeout 7200 \
  --verbose \
  "$@"
