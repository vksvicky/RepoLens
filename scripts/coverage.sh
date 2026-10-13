#!/usr/bin/env bash
# Run the full pytest suite and write a coverage report for the repolens package.
#
#   ./scripts/coverage.sh
#
# Terminal table includes missing lines. Browsable report:
#   coverage/html/index.html
# Machine-readable report:
#   coverage/coverage.xml
#
# coverage/ and .coverage are gitignored. This does not replace scripts/ci-check.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -x .venv/bin/pytest ]]; then
  PYTEST=(.venv/bin/pytest)
elif [[ -x venv/bin/pytest ]]; then
  PYTEST=(venv/bin/pytest)
else
  PYTEST=(pytest)
fi

mkdir -p coverage
echo "==> pytest with coverage (repolens)"
"${PYTEST[@]}" -q \
  --cov=repolens \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-report=xml

echo
echo "HTML report: coverage/html/index.html"
echo "XML report:  coverage/coverage.xml"
