"""FP calibrations: demote known LLM false positives when enabled via [deep]."""

from __future__ import annotations

from pathlib import Path

from repolens.config import DeepConfig, load_config
from repolens.fp_calibrations import (
    CALIBRATION_LOCAL_UI,
    CALIBRATION_SUBPROCESS_LIST,
    LOCAL_UI_TAG,
    apply_fp_calibrations,
    effective_fp_calibrations,
)
from repolens.schema import Issue, Severity


def _injection_issue(*, example: str, severity: Severity = Severity.HIGH) -> Issue:
    return Issue(
        severity=severity,
        priority="P1",
        category="sec.injection",
        file="scripts/guided/__main__.py",
        line=54,
        title="Potential Command Injection in subprocess.run",
        explanation="subprocess.run is used with user input without sanitisation.",
        impact="Arbitrary command execution.",
        recommendedFix="Use shell=False and pass argv as a list.",
        codeExample=example,
    )


def test_effective_defaults_enable_subprocess_calibration() -> None:
    assert effective_fp_calibrations(DeepConfig())[CALIBRATION_SUBPROCESS_LIST] is True


def test_config_can_disable_subprocess_calibration() -> None:
    deep = DeepConfig(fp_calibrations={CALIBRATION_SUBPROCESS_LIST: False})
    assert effective_fp_calibrations(deep)[CALIBRATION_SUBPROCESS_LIST] is False


def test_subprocess_list_form_high_demoted_to_low() -> None:
    issue = _injection_issue(
        example="proc = subprocess.run(argv, check=False)\n# argv is a list"
    )
    out = apply_fp_calibrations([issue], DeepConfig())
    assert len(out) == 1
    assert out[0].severity == Severity.LOW
    assert "[calibrated: subprocess_list_not_injection]" in out[0].explanation


def test_shell_true_not_demoted() -> None:
    issue = _injection_issue(
        example='subprocess.run("rm -rf " + path, shell=True)',
    )
    out = apply_fp_calibrations([issue], DeepConfig())
    assert out[0].severity == Severity.HIGH


def test_disabled_calibration_is_noop() -> None:
    issue = _injection_issue(
        example="subprocess.run(argv, check=False, shell=False)",
    )
    deep = DeepConfig(fp_calibrations={CALIBRATION_SUBPROCESS_LIST: False})
    out = apply_fp_calibrations([issue], deep)
    assert out[0].severity == Severity.HIGH


def test_load_fp_calibrations_from_toml(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".repolens.toml").write_text(
        "[deep]\n"
        "fp_calibrations = { subprocess_list_not_injection = false }\n",
        encoding="utf-8",
    )
    cfg = load_config(project)
    assert cfg.deep.fp_calibrations[CALIBRATION_SUBPROCESS_LIST] is False
    assert effective_fp_calibrations(cfg.deep)[CALIBRATION_SUBPROCESS_LIST] is False


def test_test_fixture_secrets_demoted() -> None:
    issue = Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="sec.repo_hygiene_secrets",
        file="tests/fixtures/fake_secrets.env",
        line=1,
        title="Hardcoded API key in fixture",
        explanation="Found sk-test in env file",
        impact="Credential exposure if shipped.",
        recommendedFix="Use placeholders",
        codeExample="API_KEY=sk-test",
    )
    out = apply_fp_calibrations([issue], DeepConfig())
    assert out[0].severity == Severity.LOW
    assert "[calibrated: test_fixture_secrets]" in out[0].explanation


def test_production_secret_path_not_demoted() -> None:
    issue = Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="gitleaks",
        file="src/app/config.py",
        line=10,
        title="Hardcoded secret",
        explanation="Live key in source",
        impact="Credential exposure.",
        recommendedFix="Use env var",
        codeExample='KEY = "sk-live"',
        source="scanner",
    )
    out = apply_fp_calibrations([issue], DeepConfig())
    assert out[0].severity == Severity.HIGH


def test_intentional_vuln_example_demoted() -> None:
    issue = Issue(
        severity=Severity.CRITICAL,
        priority="P1",
        category="sec.injection",
        file="examples/vuln_demo/app.py",
        line=3,
        title="SQL injection (intentional demo)",
        explanation="This is an intentional vulnerable example for training.",
        impact="Demo only.",
        recommendedFix="Do not ship",
        codeExample="cursor.execute('SELECT ' + user)",
    )
    out = apply_fp_calibrations([issue], DeepConfig())
    assert out[0].severity == Severity.LOW
    assert "[calibrated: intentional_vuln_example]" in out[0].explanation


def _local_ui_issue(*, explanation: str, severity: Severity = Severity.MEDIUM) -> Issue:
    return Issue(
        severity=severity,
        priority="P2",
        category="sec.data_exposure",
        file="Sources/SettingsView.swift",
        line=12,
        title="Token shown in a local UI text field",
        explanation=explanation,
        impact="A person at the screen can read the value.",
        recommendedFix="Show a placeholder.",
        codeExample="label.text = token",
    )


def test_local_ui_data_exposure_is_demoted_and_tagged() -> None:
    issue = _local_ui_issue(
        explanation="The desktop view displays the token in a text field.",
    )
    out = apply_fp_calibrations([issue], DeepConfig())
    assert out[0].severity == Severity.LOW
    assert LOCAL_UI_TAG in out[0].explanation
    assert f"[calibrated: {CALIBRATION_LOCAL_UI}]" in out[0].explanation


def test_local_ui_with_a_network_path_stays_medium() -> None:
    issue = _local_ui_issue(
        explanation="The desktop view displays the token, then URLSession uploads it.",
    )
    out = apply_fp_calibrations([issue], DeepConfig())
    assert out[0].severity == Severity.MEDIUM
    assert LOCAL_UI_TAG not in out[0].explanation


def test_local_ui_calibration_can_be_disabled() -> None:
    issue = _local_ui_issue(
        explanation="The desktop view displays the token in a text field.",
    )
    deep = DeepConfig(fp_calibrations={CALIBRATION_LOCAL_UI: False})
    out = apply_fp_calibrations([issue], deep)
    assert out[0].severity == Severity.MEDIUM
    assert effective_fp_calibrations(DeepConfig())[CALIBRATION_LOCAL_UI] is True
