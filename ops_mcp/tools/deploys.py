"""list_recent_deploys: recent GitHub Actions runs via `gh run list`, so the
Agent can test hypotheses like "images superseded by last night's deploy"
against real deploy timing instead of guessing."""

from __future__ import annotations

import json

from ops_mcp.command_runner import CommandRunner

MAX_DEPLOYS = 50
DEFAULT_DEPLOYS = 10
_JSON_FIELDS = "databaseId,displayTitle,headBranch,conclusion,createdAt,event"


def list_recent_deploys(runner: CommandRunner, limit: int = DEFAULT_DEPLOYS) -> dict:
    """Return the `limit` (hard-capped at MAX_DEPLOYS) most recent workflow runs."""
    bounded_limit = min(max(limit, 1), MAX_DEPLOYS)

    result = runner(["gh", "run", "list", "--limit", str(bounded_limit), "--json", _JSON_FIELDS])
    if not result.ok:
        raise RuntimeError(f"list_recent_deploys: `gh run list` failed: {result.stderr.strip()}")

    try:
        runs = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"list_recent_deploys: malformed `gh run list` JSON: {exc}") from exc

    bounded_runs = runs[:bounded_limit]
    return {
        "deploys": [
            {
                "id": r["databaseId"],
                "title": r["displayTitle"],
                "branch": r["headBranch"],
                "conclusion": r["conclusion"],
                "created_at": r["createdAt"],
                "event": r["event"],
            }
            for r in bounded_runs
        ],
        "count_returned": len(bounded_runs),
        "truncated": len(runs) > len(bounded_runs),
    }
