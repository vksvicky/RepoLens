# Phase 2 Multi-source Ingest Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Review remote repos via `--git-url` / `--github` with shallow clone, safe auth, cwd reports, and cleanup.

**Architecture:** `repolens.sources.SourceResolver` returns a worktree + `cleanup` flag; CLI/pipeline use it before inventory; temp dirs removed in `finally`.

**Tech Stack:** Python 3.11+, subprocess `git`, typer, pytest (mocked git/gh).

## File map

| File | Role |
|------|------|
| `src/repolens/sources.py` | URL build, auth, clone, cleanup |
| `src/repolens/pipeline.py` | Accept resolved root + report base for remotes |
| `src/repolens/cli.py` | Source flags, exit 3, cleanup |
| `tests/test_sources.py` | Unit tests |
| `tests/test_cli.py` | Flag mutual exclusion / dry-run mock |
| Docs | phases, FAQ, README, remote-sources, design, CHANGELOG |

## Tasks

1. TDD sources helpers (parse github, auth resolution, build clone argv without token in URL)
2. TDD clone+cleanup with mocked subprocess
3. Wire CLI + pipeline report path for remotes
4. Docs + phases checkboxes
5. pytest + ruff green
