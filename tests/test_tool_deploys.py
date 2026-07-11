"""list_recent_deploys: recent GitHub Actions runs via `gh run list`, so the
Agent can test "images superseded by last night's deploy" against real
deploy timing instead of guessing."""

from __future__ import annotations

import json

import pytest

from ops_mcp.command_runner import CommandResult
from ops_mcp.tools.deploys import MAX_DEPLOYS, list_recent_deploys


def _run(id_: int, branch: str = "main", conclusion: str = "success") -> dict:
    return {
        "databaseId": id_,
        "displayTitle": f"deploy {id_}",
        "headBranch": branch,
        "conclusion": conclusion,
        "createdAt": f"2026-07-{10 + id_:02d}T00:00:00Z",
        "event": "push",
    }


def _gh_command(limit: int) -> tuple[str, ...]:
    return (
        "gh", "run", "list", "--limit", str(limit), "--json",
        "databaseId,displayTitle,headBranch,conclusion,createdAt,event",
    )


def test_list_recent_deploys_happy(scripted_runner):
    runner, responses = scripted_runner
    runs = [_run(1), _run(2)]
    responses[_gh_command(10)] = CommandResult(stdout=json.dumps(runs), stderr="", returncode=0)

    result = list_recent_deploys(runner)

    assert result["count_returned"] == 2
    assert result["deploys"][0]["id"] == 1
    assert result["deploys"][0]["branch"] == "main"
    assert result["truncated"] is False


def test_list_recent_deploys_bounds_limit_at_max(scripted_runner):
    runner, responses = scripted_runner
    runs = [_run(i) for i in range(MAX_DEPLOYS)]
    responses[_gh_command(MAX_DEPLOYS)] = CommandResult(
        stdout=json.dumps(runs), stderr="", returncode=0
    )

    result = list_recent_deploys(runner, limit=10_000)

    assert result["count_returned"] == MAX_DEPLOYS


def test_list_recent_deploys_raises_clearly_on_command_failure(scripted_runner):
    runner, responses = scripted_runner
    responses[_gh_command(10)] = CommandResult(
        stdout="", stderr="gh: not authenticated", returncode=1
    )

    with pytest.raises(RuntimeError, match="gh run list"):
        list_recent_deploys(runner)


def test_list_recent_deploys_raises_on_malformed_json(scripted_runner):
    runner, responses = scripted_runner
    responses[_gh_command(10)] = CommandResult(stdout="not json", stderr="", returncode=0)

    with pytest.raises(ValueError):
        list_recent_deploys(runner)
