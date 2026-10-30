"""Post-LLM false-positive calibrations (toggleable via ``[deep].fp_calibrations``)."""

from __future__ import annotations

import re

from repolens.config import DeepConfig
from repolens.schema import Issue, Severity

CALIBRATION_SUBPROCESS_LIST = "subprocess_list_not_injection"
CALIBRATION_TEST_FIXTURE_SECRETS = "test_fixture_secrets"
CALIBRATION_INTENTIONAL_VULN = "intentional_vuln_example"
CALIBRATION_LOCAL_UI = "local_ui_attack_surface"
LOCAL_UI_TAG = "attack_surface=local_ui"

# Packaged defaults — omit key in config to use these; set false to disable.
DEFAULT_FP_CALIBRATIONS: dict[str, bool] = {
    CALIBRATION_SUBPROCESS_LIST: True,
    CALIBRATION_TEST_FIXTURE_SECRETS: True,
    CALIBRATION_INTENTIONAL_VULN: True,
    CALIBRATION_LOCAL_UI: True,
}

_INJECTION_HINT = re.compile(
    r"sec\.injection|command\s+injection|subprocess",
    re.IGNORECASE,
)
_SHELL_TRUE = re.compile(r"shell\s*=\s*True")
_SHELL_FALSE = re.compile(r"shell\s*=\s*False")
_SUBPROCESS_CALL = re.compile(
    r"subprocess\.(?:run|Popen|call|check_call|check_output)\s*\(",
    re.IGNORECASE,
)
# List / argv-style first arg (not a string literal shell command).
_LIST_OR_ARGV_FIRST = re.compile(
    r"subprocess\.(?:run|Popen|call|check_call|check_output)\s*\(\s*"
    r"(?:argv|args|cmd|command|\[[^\]]*\])",
    re.IGNORECASE,
)
_SECRET_HINT = re.compile(
    r"secret|credential|api[_ ]?key|token|password|gitleaks|hardcoded",
    re.IGNORECASE,
)
_FIXTURE_PATH = re.compile(
    r"(^|/)(tests?/fixtures?/|testdata/|fixtures/)",
    re.IGNORECASE,
)
_INTENTIONAL_HINT = re.compile(
    r"intentional|deliberate|vulnerable\s+example|vuln[_ ]?demo|"
    r"for\s+training|demo\s+only|example\s+vuln|do\s+not\s+ship",
    re.IGNORECASE,
)
_EXAMPLE_PATH = re.compile(
    r"(^|/)(examples?/|demos?/|fixtures?/vuln)",
    re.IGNORECASE,
)
_LOCAL_UI = re.compile(
    r"local[\s_-]?ui|desktop[\s_-]?(?:app|ui)|main window|ui window|"
    r"nsview|uiview|swiftui|uikit|\bcanvas\b|text field|label\.text|"
    r"clipboard|pasteboard|userdefaults|nsuserdefaults|"
    r"localstorage|sessionstorage|on-screen|view state",
    re.IGNORECASE,
)
_DATA_EXPOSURE = re.compile(
    r"data exposure|sensitive data|\bpii\b|shown in|text field|label\.text",
    re.IGNORECASE,
)
_EXFIL = re.compile(
    r"https?://|\bsocket\b|urllib|requests\.|fetch\(|webhook|\bupload\b|\bexfil|"
    r"\bipc\b|\bxpc\b|urlsession|nsurlsession|\bgrpc\b|\bnetwork\b",
    re.IGNORECASE,
)


def effective_fp_calibrations(deep: DeepConfig) -> dict[str, bool]:
    """Merge packaged defaults with ``deep.fp_calibrations`` overrides."""
    resolved = dict(DEFAULT_FP_CALIBRATIONS)
    for key, value in (deep.fp_calibrations or {}).items():
        if key in resolved:
            resolved[key] = bool(value)
        # Unknown ids ignored (forward-compatible).
    return resolved


def apply_fp_calibrations(issues: list[Issue], deep: DeepConfig) -> list[Issue]:
    """Return issues with enabled calibrations applied (demote, do not drop)."""
    enabled = effective_fp_calibrations(deep)
    out: list[Issue] = []
    for issue in issues:
        current = issue
        if enabled.get(CALIBRATION_SUBPROCESS_LIST):
            current = _calibrate_subprocess_list(current)
        if enabled.get(CALIBRATION_TEST_FIXTURE_SECRETS):
            current = _calibrate_test_fixture_secrets(current)
        if enabled.get(CALIBRATION_INTENTIONAL_VULN):
            current = _calibrate_intentional_vuln(current)
        if enabled.get(CALIBRATION_LOCAL_UI):
            current = _calibrate_local_ui(current)
        out.append(current)
    return out


def _issue_text(issue: Issue) -> str:
    return "\n".join(
        [
            issue.category,
            issue.title,
            issue.explanation,
            issue.codeExample,
            issue.recommendedFix,
        ]
    )


def _demote(issue: Issue, calibration_id: str) -> Issue:
    if issue.severity not in {Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM}:
        return issue
    prefix = f"[calibrated: {calibration_id}]"
    explanation = issue.explanation
    if prefix not in explanation:
        explanation = f"{prefix} {explanation}"
    return issue.model_copy(
        update={
            "severity": Severity.LOW,
            "explanation": explanation,
        }
    )


def _looks_like_safe_list_subprocess(text: str) -> bool:
    if not _SUBPROCESS_CALL.search(text):
        return False
    if _SHELL_TRUE.search(text):
        return False
    if _LIST_OR_ARGV_FIRST.search(text):
        return True
    if _SHELL_FALSE.search(text):
        return True
    return False


def _calibrate_subprocess_list(issue: Issue) -> Issue:
    text = _issue_text(issue)
    if not _INJECTION_HINT.search(text):
        return issue
    if not _looks_like_safe_list_subprocess(text):
        return issue
    return _demote(issue, CALIBRATION_SUBPROCESS_LIST)


def _calibrate_test_fixture_secrets(issue: Issue) -> Issue:
    # Prefer not to demote scanner-confirmed secrets outside fixtures
    path = (issue.file or "").replace("\\", "/")
    if not _FIXTURE_PATH.search(path):
        return issue
    text = _issue_text(issue)
    if not _SECRET_HINT.search(text) and "secret" not in (issue.category or "").lower():
        return issue
    return _demote(issue, CALIBRATION_TEST_FIXTURE_SECRETS)


def _calibrate_intentional_vuln(issue: Issue) -> Issue:
    path = (issue.file or "").replace("\\", "/")
    text = _issue_text(issue)
    path_hit = bool(_EXAMPLE_PATH.search(path))
    text_hit = bool(_INTENTIONAL_HINT.search(text))
    if not (path_hit and text_hit):
        return issue
    return _demote(issue, CALIBRATION_INTENTIONAL_VULN)


def _tag_local_ui(issue: Issue) -> Issue:
    if LOCAL_UI_TAG in issue.explanation:
        return issue
    explanation = issue.explanation.rstrip()
    spacer = " " if explanation else ""
    return issue.model_copy(update={"explanation": f"{explanation}{spacer}{LOCAL_UI_TAG}"})


def _calibrate_local_ui(issue: Issue) -> Issue:
    """Demote a local-only UI exposure that has no network or IPC path."""
    text = _issue_text(issue)
    if _EXFIL.search(text):
        return issue
    if not _LOCAL_UI.search(text) or not _DATA_EXPOSURE.search(text):
        return issue
    tagged = _tag_local_ui(issue)
    if tagged.severity == Severity.LOW:
        return tagged
    return _demote(tagged, CALIBRATION_LOCAL_UI)
