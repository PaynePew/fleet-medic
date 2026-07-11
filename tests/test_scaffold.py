"""Scaffold invariants for the fleet-medic repo (Phase 1 slice 1).

No feature code lands in this slice — its job is to prove the uv + pytest +
ruff + CI harness actually works before any merge-ladder semantics can exist
(roadmap.md, PRD "repo 腳手架"). These tests exercise that harness against a
couple of hard constraints from CLAUDE.md that are cheap to check mechanically
rather than trusting review alone.
"""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_pins_python_312():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["requires-python"] == ">=3.12"


def test_gitignore_excludes_run_ledgers():
    # Hard constraint (CLAUDE.md / .gitignore comment): run ledgers are Actions
    # artifacts and must never be committed to the repo.
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "ledgers/" in gitignore


def test_bootstrap_docs_present_and_nonempty():
    # CLAUDE.md's "讀我之後先讀" list: a fresh session needs these to exist
    # with real content before it can orient itself.
    required = [
        "CONTEXT.md",
        "project-docs/roadmap.md",
        "project-docs/architecture/system-overview.md",
        "project-docs/adr/0001-llm-never-in-the-polling-loop.md",
        "project-docs/adr/0002-agent-lives-off-box.md",
    ]
    for rel_path in required:
        path = REPO_ROOT / rel_path
        assert path.is_file(), f"missing bootstrap doc: {rel_path}"
        assert path.stat().st_size > 0, f"bootstrap doc is empty: {rel_path}"
