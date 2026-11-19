#!/usr/bin/env bash
# Full combined review, then one HTML file for that run.
#
#   ./scripts/selfdog-review.sh
#   ./scripts/selfdog-review.sh full
#   ./scripts/selfdog-review.sh html reports/selfdog-deep/gate_review_report_review_YYYY-MM-DD_HHMM.md
#   TARGET=/path/to/other/tree ./scripts/selfdog-review.sh
#   ./scripts/selfdog-review.sh --dry-run
#
# Reviews this checkout. When TARGET is set, reviews that tree instead and
# still writes the report under reports/selfdog-deep in this checkout.
# The dev install may point at another checkout. PYTHONPATH keeps this
# checkout's src first. Often an hour or more on local qwen2.5-coder:32b.
# Extra flags are added at the end of the review. --timeout 7200 is the
# longest one model pass may run. --dry-run counts files and does not write HTML.
set -euo pipefail
cd "$(dirname "$0")/.."

review_path="${TARGET:-.}"
out_dir="reports/selfdog-deep"
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

show_menu() {
  cat <<'EOF'
RepoLens selfdog

  1  full
     Full review, then one HTML file for that run. Often an hour or more.
     repolens review --path "$TARGET" --out reports/selfdog-deep --full --full-audit --deep --scanners gitleaks,semgrep,osv,trivy,checkov --model qwen2.5-coder:32b --timeout 7200 --verbose

  2  html [report.md]
     HTML only, for a report you already have. Omit the file to use the newest run in reports/selfdog-deep.
     repolens export <report.md> --report-html <report.html>

  3  changed
     This change-set. One deep pass. Scanners still see the whole tree.
     repolens review --path "$TARGET" --out reports/selfdog-deep --full-audit --deep --deep-passes 1 --git-diff auto --scanners gitleaks,semgrep,osv,trivy,checkov --model qwen2.5-coder:32b --timeout 1800 --verbose

  4  short
     One deep pass. Markdown and JSON. No scanners unless you add them.
     repolens review --path "$TARGET" --out reports/selfdog-deep --full-audit --deep --deep-passes 1 --model qwen2.5-coder:32b --timeout 3600 --verbose --format both

  5  fast
     Scanners and measurements only. No model.
     repolens review --path "$TARGET" --out reports/selfdog-deep --scanners-only --scanners gitleaks,semgrep,osv,trivy,checkov --sarif --verbose

Choice [1-5]:
TARGET sets the tree under review. The report still lands in reports/selfdog-deep here.
--dry-run counts files and does not write HTML. Extra flags after a choice are added to that review.
EOF
}

ask_choice() {
  local picked=""
  while true; do
    read -r -p "Choice [1-5]: " picked
    case "$picked" in
      1|full) choice="full"; return ;;
      2|html) choice="html"; return ;;
      3|changed) choice="changed"; return ;;
      4|short) choice="short"; return ;;
      5|fast) choice="fast"; return ;;
      q|quit) exit 0 ;;
      *) echo "Enter 1, 2, 3, 4, or 5." ;;
    esac
  done
}

latest_report() {
  local latest="" f
  shopt -s nullglob
  for f in "$out_dir"/gate_review_report_*.json; do
    [[ "$f" == *.sarif.json ]] && continue
    if [[ -z "$latest" || "$f" > "$latest" ]]; then
      latest=$f
    fi
  done
  shopt -u nullglob
  printf '%s\n' "$latest"
}

write_html() {
  local report="$1" dest="$1"
  dest="${dest%.json}"
  dest="${dest%.md}.html"
  "${REPOLENS[@]}" export "$report" --report-html "$dest"
}

choice=""
if [[ $# -eq 0 ]]; then
  show_menu
  if [[ -t 0 ]]; then
    ask_choice
  else
    exit 0
  fi
else
  case "$1" in
    menu|--menu|--help|-h)
      show_menu
      if [[ -t 0 ]]; then
        ask_choice
        shift
      else
        exit 0
      fi
      ;;
    full|html|changed|short|fast)
      choice="$1"
      shift
      ;;
    -*) choice="full" ;;
    *)
      echo "Unknown choice: $1" >&2
      show_menu
      exit 2
      ;;
  esac
fi

if [[ "$choice" == "html" ]]; then
  report=""
  if [[ $# -gt 0 && "$1" != -* ]]; then
    report="$1"
    shift
  fi
  if [[ $# -gt 0 ]]; then
    echo "html takes only the report file." >&2
    exit 2
  fi
  if [[ -z "$report" ]]; then
    report="$(latest_report)"
  fi
  if [[ -z "$report" ]]; then
    echo "No gate_review_report_*.json under $out_dir" >&2
    exit 2
  fi
  write_html "$report"
  exit 0
fi

case "$choice" in
  full|changed|short|fast) ;;
  *)
    echo "Unknown choice: $choice" >&2
    show_menu
    exit 2
    ;;
esac

dry=0
for arg in "$@"; do
  if [[ "$arg" == "--dry-run" ]]; then
    dry=1
  fi
done

args=(review --path "$review_path" --out reports/selfdog-deep)
case "$choice" in
  full)
    args+=(
      --full --full-audit --deep
      --scanners gitleaks,semgrep,osv,trivy,checkov
      --model qwen2.5-coder:32b --timeout 7200 --verbose
    )
    ;;
  changed)
    args+=(
      --full-audit --deep --deep-passes 1 --git-diff auto
      --scanners gitleaks,semgrep,osv,trivy,checkov
      --model qwen2.5-coder:32b --timeout 1800 --verbose
    )
    ;;
  short)
    args+=(
      --full-audit --deep --deep-passes 1
      --model qwen2.5-coder:32b --timeout 3600 --verbose --format both
    )
    ;;
  fast)
    args+=(--scanners-only --scanners gitleaks,semgrep,osv,trivy,checkov --sarif --verbose)
    ;;
esac

set +e
"${REPOLENS[@]}" "${args[@]}" "$@"
status=$?
set -e
if [[ "$status" -eq 2 || "$dry" -eq 1 ]]; then
  exit "$status"
fi
report="$(latest_report)"
if [[ -z "$report" ]]; then
  echo "Review finished and left no gate report to export." >&2
  exit "$status"
fi
set +e
write_html "$report"
html_status=$?
set -e
if [[ "$status" -ne 0 ]]; then
  exit "$status"
fi
exit "$html_status"
