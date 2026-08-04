# Phase 5 Adaptive SQLite + FTS5 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement this plan task-by-task.

**Goal:** Unified `.repolens/repolens.sqlite` with always-on fingerprints/runs/meta and opt-in FTS5 `chunks`; wire progressive pack selection + per-project timeout recommendations into `run_review`.

**Architecture:** One SQLite file; `ProjectStore` owns schema/migrations; `LearningIndex` uses the same DB for FTS; adaptive sync classifies file changes and recommends timeout.

**Tech stack:** Python 3.11+, stdlib `sqlite3` FTS5, existing inventory/pipeline/cli, pytest.

---

### Task 1: ProjectStore schema + migrate `index.sqlite`

**Files:**
- Create: `src/repolens/learning/store.py`
- Create: `tests/test_project_store.py`
- Modify: `src/repolens/learning/index.py` (use store DB path)

**Steps:** Create failing tests for open/create tables, migrate chunks from legacy `index.sqlite`, fingerprint upsert. Implement `ProjectStore`. Point `index_db_path` / LearningIndex at unified path with migration. Commit when green.

### Task 2: Fingerprint sync + timeout recommendation

**Files:**
- Create: `src/repolens/adaptive.py` (or `learning/adaptive.py`)
- Create: `tests/test_adaptive.py`
- Modify: `src/repolens/config.py` — `AdaptiveConfig`

**Steps:** TDD `sync_fingerprints` → added/changed/deleted; `recommend_timeout` from runs + heuristics; config load.

### Task 3: Wire `run_review`

**Files:**
- Modify: `src/repolens/pipeline.py`
- Modify: `tests/test_pipeline.py` / new tests

**Steps:** If adaptive enabled: sync, select pack, apply timeout, record run; progress lines; `--full` forces full pack.

### Task 4: Incremental FTS + CLI `adaptive status`

**Files:**
- Modify: `src/repolens/learning/index.py` — upsert/delete paths
- Modify: `src/repolens/cli.py`
- Docs: FAQ, local-learning, try-on, CHANGELOG, phases checkboxes

**Steps:** When consented, sync chunks for changed paths; add `repolens adaptive status`; document.

---

**Spec:** [docs/design/phase-5-adaptive-cache-and-recommendations.md](../../design/phase-5-adaptive-cache-and-recommendations.md)
