"""Deep multi-pass planner, file budgeting, merge/dedupe, and prompt builder.

Char budgeting uses ``FileEntry.size`` (bytes) as a character-cost estimate so
planning does not read file contents. Callers that later pack prompts should
still use ``read_excerpt`` (or the same size estimate) consistently with this
budget so selected files fit the pass cap.

This module is a thin re-export façade. Implementations live in
``deep_types``, ``deep_budget``, ``deep_plan``, ``deep_merge``, and
``deep_prompt``.
"""

from __future__ import annotations

from repolens.deep_budget import budget_files
from repolens.deep_merge import is_unmeasured_model_claim, merge_reports
from repolens.deep_plan import plan_deep_passes
from repolens.deep_prompt import build_deep_prompt
from repolens.deep_types import (
    DeepPass,
    compact_pass_summary,
    coverage_checklist_tail,
    coverage_closure_prompt,
    entry_matches_cycle,
    estimate_outline_chars,
    module_name_forms,
)

__all__ = [
    "DeepPass",
    "budget_files",
    "build_deep_prompt",
    "compact_pass_summary",
    "coverage_checklist_tail",
    "coverage_closure_prompt",
    "entry_matches_cycle",
    "estimate_outline_chars",
    "is_unmeasured_model_claim",
    "merge_reports",
    "module_name_forms",
    "plan_deep_passes",
]
