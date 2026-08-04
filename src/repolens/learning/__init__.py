"""Opt-in local learning (on-disk index + memory)."""

from repolens.learning.consent import (
    CONSENT_NOTICE,
    accept_local_learning,
    ensure_consent,
    has_consent,
)
from repolens.learning.index import LearningIndex, clear_index
from repolens.learning.memory import LearningMemory
from repolens.learning.retrieve import retrieve_context

__all__ = [
    "CONSENT_NOTICE",
    "LearningIndex",
    "LearningMemory",
    "accept_local_learning",
    "clear_index",
    "ensure_consent",
    "has_consent",
    "retrieve_context",
]
