"""Scanner catalog rejection."""

from __future__ import annotations

import pytest

from repolens.scanners.runner import parse_scanners_flag


def test_parse_scanners_flag_rejects_nmap() -> None:
    with pytest.raises(ValueError, match="nmap"):
        parse_scanners_flag("nmap", config_enabled=[])
