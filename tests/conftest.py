"""Test harness setup for ops_mcp.

Repo root isn't installed as a package (`pyproject.toml` keeps
`[tool.uv] package = false` — the app runs in place, it isn't distributed),
so tests add it to sys.path here instead of fighting that scaffold decision.

Also provides `scripted_runner`: the injected command-runner double every
ops_mcp tool test uses in place of a real shell/SSH call (CODING_STANDARDS
§4 — SSH/shell execution is a seam, real processes never run in unit tests).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest  # noqa: E402

from ops_mcp.command_runner import CommandResult  # noqa: E402


@pytest.fixture
def scripted_runner():
    """Yields (runner, responses).

    Script expected commands before calling the tool under test:
        responses[("df", "-P", "/")] = CommandResult(stdout=..., stderr="", returncode=0)

    Any command not pre-scripted raises AssertionError immediately, so a
    test's command list is a complete, checkable spec of what the tool runs.
    """
    responses: dict[tuple[str, ...], CommandResult] = {}

    def run(command: list[str]) -> CommandResult:
        key = tuple(command)
        if key not in responses:
            raise AssertionError(f"scripted_runner: unscripted command {command!r}")
        return responses[key]

    return run, responses
