"""The selfdog script reviews the checkout it lives in."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_selfdog_review_runs_the_full_audit_on_this_checkout() -> None:
    text = (ROOT / "scripts" / "selfdog-review.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert 'cd "$(dirname "$0")/.."' in text
    assert 'review_path="${TARGET:-.}"' in text
    assert 'export PYTHONPATH="$PWD/src' in text
    for flag in (
        "--out reports/selfdog-deep",
        "--full",
        "--full-audit",
        "--deep",
        "--scanners gitleaks,semgrep,osv,trivy,checkov",
        "--model qwen2.5-coder:32b",
        "--timeout 7200",
        "--verbose",
    ):
        assert flag in text
    assert "PatternSorcerer" not in text
    assert '"$@"' in text
    assert "Often an hour or more" in text
