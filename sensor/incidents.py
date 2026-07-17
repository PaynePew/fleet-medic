"""incidents: sensor-side gh issue queries. GitHub Issues are the sensor's
only durable store across stateless Actions runs (roadmap.md arch-review
#5: "Actions 無狀態,issue 即狀態儲存") — one `gh issue list` call here backs
dedup, the daily budget count, and the tripwire's armed/disarmed state."""

from __future__ import annotations

import json
from datetime import date

from ops_mcp.command_runner import CommandRunner, run_checked

DEFAULT_LIST_LIMIT = 100
MAX_LIST_LIMIT = 200
_JSON_FIELDS = "number,state,createdAt"


def list_incidents(
    runner: CommandRunner, label: str, limit: int = DEFAULT_LIST_LIMIT
) -> list[dict]:
    """Return every open+closed issue carrying `label`, hard-capped at
    MAX_LIST_LIMIT."""
    bounded_limit = min(max(limit, 1), MAX_LIST_LIMIT)
    command = [
        "gh", "issue", "list", "--state", "all", "--label", label,
        "--json", _JSON_FIELDS, "--limit", str(bounded_limit),
    ]
    result = run_checked(runner, command, f"list_incidents({label!r}): `gh issue list` failed")

    try:
        issues = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"list_incidents({label!r}): malformed `gh issue list` JSON: {exc}"
        ) from exc
    return issues


def has_open_incident(issues: list[dict]) -> bool:
    """True while at least one issue in `issues` is still open — the dedup
    gate: a live incident already covers whatever the sensor would
    otherwise re-trip on (roadmap.md arch-review #5: 去重)."""
    return any(issue["state"] == "OPEN" for issue in issues)


def count_created_on(issues: list[dict], day: date) -> int:
    """How many issues in `issues` were created on `day` — the daily
    budget gate's spawn count for that day."""
    prefix = day.isoformat()
    return sum(1 for issue in issues if issue["createdAt"][:10] == prefix)


def derive_armed_state(issues: list[dict]) -> bool:
    """The tripwire's armed bit, derived from gh issue state — there is no
    separate state store, because Actions is stateless and issue state is
    the store this project chose (roadmap.md arch-review #5). An open
    incident is the disarmed state outright (dedup); closing it rearms.

    Known simplification, not a silent gap: full Schmitt-trigger hysteresis
    (sensor.tripwire.evaluate_tripwire) rearms only once a *later* tick
    observes disk_percent < low, which requires an armed bit that persists
    across ticks. A closed GitHub issue can't carry that distinction — it
    looks the same whether it closed a second ago (box still hovering near
    `high`) or a week ago. evaluate_tripwire is fully implemented and
    tested as that primitive, ready to wire in once a per-tick persisted
    store exists (e.g. a dedicated tracking issue/label); until then, an
    incident closing is this tracer bullet's rearm signal, and the
    dedup-while-open check above is what actually prevents flapping.
    """
    return not has_open_incident(issues)
