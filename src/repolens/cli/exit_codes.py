"""Process status codes for the CLI.

``EXIT_BAD_INPUT`` is usage and bad arguments. ``EXIT_NOT_READY`` is a check
that cannot finish (missing baseline, graph ratchet, blocked architecture gate).
``JSON_INDENT`` is the indent for machine-readable command output.
"""

from __future__ import annotations

EXIT_BAD_INPUT = 2
EXIT_NOT_READY = 3
JSON_INDENT = 2
