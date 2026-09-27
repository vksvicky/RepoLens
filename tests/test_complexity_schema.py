# tests/test_complexity_schema.py
"""B1 — ComplexityBlock / hotspot schema for Top-10 report table."""

from __future__ import annotations

from repolens.schema import ComplexityBlock, ComplexityHotspot, FindingReport, Summary


def test_complexity_block_on_report() -> None:
    block = ComplexityBlock(
        functionsAnalysed=100,
        issueCount=3,
        maxCyclomatic=55,
        maxCognitive=40,
        p95Cyclomatic=18,
        p95Cognitive=22,
        hotspots=[
            ComplexityHotspot(
                file="a.py",
                function="monster",
                line=10,
                cyclomatic=55,
                cognitive=40,
            )
        ],
    )
    report = FindingReport(confidence=80, summary=Summary(), complexity=block)
    assert report.complexity is not None
    assert len(report.complexity.hotspots) == 1
    assert report.complexity.hotspots[0].function == "monster"
