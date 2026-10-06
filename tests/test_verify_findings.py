"""Phase 6.9: opt-in Critical location verify (non-fatal)."""

from __future__ import annotations

from pathlib import Path

from repolens.config import DeepConfig
from repolens.schema import Issue, Severity
from repolens.verify_findings import apply_verify_findings


def test_verify_marks_unverified_critical(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    issue = Issue(
        severity=Severity.CRITICAL,
        priority="P1",
        category="sec.injection",
        file="a.py",
        line=99,
        title="Bad",
        explanation="x",
        impact="Attacker may exploit this.",
        recommendedFix="fix",
        codeExample="return safe()",
        source="llm",
        anchorQuote="this quote is not in the file",
        locationVerified=False,
    )
    out = apply_verify_findings(tmp_path, [issue], DeepConfig(verify_findings=True))
    assert "[verify: location unconfirmed]" in out[0].explanation
    assert out[0].locationVerified is False


def test_verify_off_is_noop(tmp_path: Path) -> None:
    issue = Issue(
        severity=Severity.CRITICAL,
        priority="P1",
        category="sec.injection",
        file="missing.py",
        line=1,
        title="Bad",
        explanation="plain",
        impact="Attacker may exploit this.",
        recommendedFix="fix",
        codeExample="return safe()",
        source="llm",
        locationVerified=False,
    )
    out = apply_verify_findings(tmp_path, [issue], DeepConfig(verify_findings=False))
    assert out[0].explanation == "plain"


def test_verify_js_function_symbol_is_grounded(tmp_path: Path) -> None:
    (tmp_path / "login.js").write_text(
        "function handleLogin(req) {\n  return req.user;\n}\n",
        encoding="utf-8",
    )
    issue = Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="sec.auth",
        file="login.js",
        line=2,
        title="handleLogin misses a CSRF check",
        explanation="handleLogin trusts the session cookie.",
        impact="Session fixation.",
        recommendedFix="Verify origin.",
        codeExample="handleLogin(req)",
        source="llm",
        locationVerified=False,
        anchorQuote="return req.user",
    )
    out = apply_verify_findings(tmp_path, [issue], DeepConfig(verify_findings=True))
    assert out[0].verificationStatus == "grounded"
    assert "[verify:" not in out[0].explanation


def test_verify_js_arrow_symbol_is_grounded(tmp_path: Path) -> None:
    (tmp_path / "auth.ts").write_text(
        "const loadUser = (id) => {\n  return db.get(id);\n};\n",
        encoding="utf-8",
    )
    issue = Issue(
        severity=Severity.CRITICAL,
        priority="P1",
        category="sec.auth",
        file="auth.ts",
        line=2,
        title="loadUser has no authz",
        explanation="loadUser returns any row.",
        impact="IDOR.",
        recommendedFix="Check caller.",
        codeExample="loadUser(id)",
        source="llm",
        locationVerified=False,
        anchorQuote="return db.get(id)",
    )
    out = apply_verify_findings(tmp_path, [issue], DeepConfig(verify_findings=True))
    assert out[0].verificationStatus == "grounded"
