"""FP calibrations: demote known LLM false positives when enabled via [deep]."""

from __future__ import annotations

from pathlib import Path

from repolens.config import DeepConfig, load_config
from repolens.fp_calibrations import (
    CALIBRATION_SUBPROCESS_LIST,
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
