"""Provenance lines in the Markdown report."""

from __future__ import annotations

from repolens.report_sections import _render_provenance_section
from repolens.schema import FindingReport, ProvenanceBlock, Summary


def test_provenance_section_renders_command_and_expanded_argv() -> None:
    report = FindingReport(
        confidence=70,
        summary=Summary(),
        issues=[],
        provenance=ProvenanceBlock(
            repoLensVersion="0.1.2",
            command="repolens audit --path .",
            expandedArgv=[
                "repolens",
                "review",
                "--path",
                ".",
                "--full",
                "--full-audit",
                "--deep",
                "--timeout",
                "3600",
                "--ratchet",
                "--verify-findings",
            ],
        ),
    )
    text = "\n".join(_render_provenance_section(report))
    assert "- **Command**: `repolens audit --path .`" in text
    assert (
        "- **Expanded argv**: `repolens review --path . --full --full-audit "
        "--deep --timeout 3600 --ratchet --verify-findings`"
    ) in text
