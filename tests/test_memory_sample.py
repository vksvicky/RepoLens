"""Python process peak RSS is a byte count, not an Ollama measurement."""

from __future__ import annotations

from repolens.memory_sample import (
    PYTHON_RSS_NOTE,
    format_peak_rss,
    peak_rss_bytes,
    vm_rss_bytes_from_status,
)
from repolens.report_sections import _provenance_identity_lines
from repolens.schema import ProvenanceBlock


def test_darwin_ru_maxrss_is_already_bytes() -> None:
    assert peak_rss_bytes(100, "darwin") == 100


def test_linux_ru_maxrss_is_kilobytes() -> None:
    assert peak_rss_bytes(100, "linux") == 100 * 1024


def test_vm_rss_status_line_is_kilobytes() -> None:
    text = "Name:\tpython\nVmRSS:\t  2048 kB\nVmSize:\t  4096 kB\n"
    assert vm_rss_bytes_from_status(text) == 2048 * 1024


def test_vm_rss_missing_line_is_none() -> None:
    assert vm_rss_bytes_from_status("Name:\tpython\n") is None


def test_format_peak_rss_uses_mebibytes() -> None:
    assert format_peak_rss(2 * 1024 * 1024) == "Python process peak RSS: 2.0 MB"


def test_provenance_omits_rss_when_the_sample_is_missing() -> None:
    lines = _provenance_identity_lines(ProvenanceBlock())
    assert all("Python process peak RSS" not in line for line in lines)


def test_provenance_names_python_peak_rss_not_the_model() -> None:
    prov = ProvenanceBlock(pythonPeakRssBytes=2 * 1024 * 1024, pythonRssNote=PYTHON_RSS_NOTE)
    lines = _provenance_identity_lines(prov)
    assert "- **Python process peak RSS**: `2.0 MB`" in lines
    assert any("not the Ollama model" in line for line in lines)
