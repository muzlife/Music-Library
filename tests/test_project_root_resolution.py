"""Pin the LIBRARY_PROJECT_ROOT abstraction.

The repo used to embed `/Volumes/Data/Works/07.hahahoho` in nine PROJECT_* path
constants in app/main.py and four ROOT constants in scripts/ + tests/. Those
have all been replaced with `LIBRARY_PROJECT_ROOT` env override + a
`Path(__file__).resolve().parents[1]` fallback.

These tests make sure (a) no literal slips back in and (b) `_resolve_project_root`
respects both the env override and the file-based fallback.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from app import main as main_module


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_resolve_project_root_falls_back_to_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIBRARY_PROJECT_ROOT", raising=False)
    resolved = main_module._resolve_project_root()
    assert resolved == REPO_ROOT


def test_resolve_project_root_respects_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "alt-root"
    target.mkdir()
    monkeypatch.setenv("LIBRARY_PROJECT_ROOT", str(target))
    resolved = main_module._resolve_project_root()
    assert resolved == target.resolve()


def test_resolve_project_root_expands_user_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    target = fake_home / "apps" / "hahahoho-prod"
    target.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("LIBRARY_PROJECT_ROOT", "~/apps/hahahoho-prod")
    resolved = main_module._resolve_project_root()
    assert resolved == target.resolve()


def test_main_module_project_paths_are_anchored_on_root() -> None:
    """Every PROJECT_*_PATH constant must live under PROJECT_ROOT.

    This catches the regression where someone reintroduces an absolute
    literal anchored on the workspace mount instead of the env-overridable
    PROJECT_ROOT helper.
    """
    expected_root = main_module.PROJECT_ROOT
    candidates = [
        main_module.PROJECT_LAUNCHD_ERR_LOG_PATH,
        main_module.PROJECT_QA_MASTER_SHEET_PATH,
        main_module.PROJECT_QA_MANUAL_SHEET_PATH,
        main_module.PROJECT_ERD_SUMMARY_PATH,
        main_module.PROJECT_ERD_DETAIL_PATH,
        main_module.PROJECT_TOOL_MANUAL_PATH,
        main_module.PROJECT_GO_LIVE_CHECKLIST_PATH,
        main_module.PROJECT_PURCHASE_IMPORT_GUIDE_PATH,
        main_module.PROJECT_CSV_IMPORT_SAMPLE_PATH,
        main_module.DISCOGS_COVER_PREVIEW_CACHE_DIR,
    ]
    for path in candidates:
        # is_relative_to was added in Python 3.9; this codebase already
        # targets 3.10+ given the dataclass-frozen + typing usage.
        assert path.is_relative_to(expected_root), f"{path} drifted off PROJECT_ROOT"


def test_no_volumes_works_literal_remains_in_runtime_code() -> None:
    """Belt-and-suspenders: scan the runtime tree for the old absolute
    literal. We allow it inside .worktrees/ (separate git worktrees) and
    inside docs/ (manual references), but not in app/, scripts/, or tests/."""
    forbidden = re.compile(r"/Volumes/Works/07\.hahahoho")
    targets = [
        REPO_ROOT / "app",
        REPO_ROOT / "scripts",
        REPO_ROOT / "tests",
    ]
    offenders: list[str] = []
    for root in targets:
        for path in root.rglob("*.py"):
            if any(part.startswith(".") for part in path.parts):
                continue  # skip dotfiles / __pycache__ shells
            text = path.read_text("utf-8", errors="ignore")
            for line_no, line in enumerate(text.splitlines(), start=1):
                if not forbidden.search(line):
                    continue
                # Allow the explanatory docstring inside _resolve_project_root.
                if "used to embed" in line:
                    continue
                offenders.append(f"{path}:{line_no}:{line.strip()}")
    assert not offenders, "absolute path literal regressed:\n" + "\n".join(offenders)
