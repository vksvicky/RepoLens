"""``repolens which`` prints a frozen command catalog."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from repolens.cli import app

runner = CliRunner()

_COMMANDS = {
    "pr": "repolens review --preset pr --path .",
    "changed": "repolens review --preset changed --path .",
    "release": "repolens review --preset release --path .",
    "audit": "repolens audit --path .",
    "m-and-a": "repolens audit --path .",
    "security": "repolens sentinel --path .",
    "architecture": "repolens architecture --path .",
}

_WHY = {
    "pr": "--no-deep",
    "changed": "900",
    "release": "3600",
    "audit": "ratchet",
    "m-and-a": "ratchet",
    "security": "P1",
    "architecture": "P3",
}


def test_which_prints_each_catalog_command() -> None:
    for scenario, command in _COMMANDS.items():
        result = runner.invoke(app, ["which", scenario])
        assert result.exit_code == 0, result.output
        assert result.stdout.strip() == command


def test_which_explain_includes_rationale() -> None:
    result = runner.invoke(app, ["which", "--explain", "release"])
    assert result.exit_code == 0, result.output
    assert "repolens review --preset release --path ." in result.stdout
    assert "3600" in result.stdout


def test_which_json_shape() -> None:
    result = runner.invoke(app, ["which", "pr", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["scenario"] == "pr"
    assert payload["command"] == _COMMANDS["pr"]
    assert _WHY["pr"] in payload["why"]


def test_which_unknown_scenario_exits_2() -> None:
    result = runner.invoke(app, ["which", "nosuch"])
    assert result.exit_code == 2
    assert "pr" in result.output
    assert "architecture" in result.output
