#!/usr/bin/env python3
"""Interactive guided helper for building and running a repolens command."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `import guided` when launched as scripts/repolens_guided.py
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from guided import *  # noqa: F403
from guided.__main__ import main
from guided.caps import subprocess, urllib  # noqa: F401 — historic test patch targets

if __name__ == "__main__":
    raise SystemExit(main())
