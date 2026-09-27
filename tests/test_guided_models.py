from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from repolens_guided import list_installed_models  # noqa: E402


def test_list_installed_models_prefers_ollama_list() -> None:
    with patch("guided.caps.subprocess.run") as run:
        run.return_value = MagicMock(
            returncode=0,
            stdout="NAME\nqwen2.5:7b\n",
            stderr="",
        )
        with patch("guided.caps.urllib.request.urlopen") as urlopen:
            assert list_installed_models() == ["qwen2.5:7b"]
            urlopen.assert_not_called()


def test_list_installed_models_falls_back_to_tags_api() -> None:
    with patch("guided.caps.subprocess.run") as run:
        run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        with patch("guided.caps.urllib.request.urlopen") as urlopen:
            resp = MagicMock()
            resp.read.return_value = b'{"models":[{"name":"fallback:1b"}]}'
            resp.__enter__.return_value = resp
            resp.__exit__.return_value = None
            urlopen.return_value = resp
            assert list_installed_models() == ["fallback:1b"]
