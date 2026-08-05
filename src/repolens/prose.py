"""Shared prose conventions for LLM prompts and generated reports."""

from __future__ import annotations

# Instruct models so finding text matches report chrome (British English).
BRITISH_ENGLISH_INSTRUCTION = (
    "Write all human-readable report fields (title, explanation, impact, "
    "recommendedFix, codeExample comments, durabilityGaps, coverage N/A reasons, "
    "and notes) in British English "
    "(e.g. behaviour, organise, analyse, prioritise, defence, licence)."
)
