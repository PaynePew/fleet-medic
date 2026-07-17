"""sensor.main.run_tick: one full sensor tick — read vitals, derive armed
state + budget from gh issue history, decide, and (only when spawning)
build and sanitize the Anomaly Snapshot. The only I/O is through the two
injected CommandRunners, so the whole tick is unit-testable without a real
SSH/gh call (issue #4 AC)."""

from __future__ import annotations

import json
from datetime import date

from ops_mcp.command_runner import CommandResult
from ops_mcp.tools.vitals import DF_COMMAND, PS_IDS_COMMAND, inspect_command
from sensor.main import INCIDENT_LABEL, run_tick

TODAY = date(2026, 7, 18)


def _make_runner(responses: dict) -> callable:
    def run(command: list[str]):
        key = tuple(command)
        if key not in responses:
            raise AssertionError(f"unscripted command {command!r}")
        return responses[key]

    return run


def _df_output(percent: str) -> str:
    return (
        "Filesystem     1024-blocks     Used Available Capacity Mounted on\n"
        f"/dev/sda1         20642428 17332708   2242496      {percent}% /\n"
    )


def _script_vitals(responses: dict, percent: str, services: list[tuple[str, bool, int]]) -> None:
    ids = [f"id{i}" for i in range(len(services))]
    responses[tuple(DF_COMMAND)] = CommandResult(
        stdout=_df_output(percent), stderr="", returncode=0
    )
    responses[tuple(PS_IDS_COMMAND)] = CommandResult(
        stdout=("\n".join(ids) + "\n" if ids else ""), stderr="", returncode=0
    )
    if ids:
        lines = [
            f"/{name}::{'running' if running else 'exited'}::{restarts}"
            for name, running, restarts in services
        ]
        responses[tuple(inspect_command(ids))] = CommandResult(
            stdout="\n".join(lines), stderr="", returncode=0
        )


def _gh_command(limit: int = 100) -> tuple[str, ...]:
    return (
        "gh", "issue", "list", "--state", "all", "--label", INCIDENT_LABEL,
        "--json", "number,state,createdAt", "--limit", str(limit),
    )


def _script_incidents(responses: dict, issues: list[dict]) -> None:
    responses[_gh_command()] = CommandResult(stdout=json.dumps(issues), stderr="", returncode=0)


def test_run_tick_spawns_and_returns_sanitized_snapshot_when_tripped():
    vitals_responses: dict = {}
    gh_responses: dict = {}
    _script_vitals(vitals_responses, "89", [("crash-looping", False, 9)])
    vitals_responses[("docker", "logs", "--tail", "200", "--timestamps", "crash-looping")] = (
        CommandResult(stdout="fetch failed from 10.0.0.5\n", stderr="", returncode=0)
    )
    _script_incidents(gh_responses, [])

    result = run_tick(
        _make_runner(vitals_responses),
        _make_runner(gh_responses),
        today=TODAY,
        host="box.example.com",
    )

    assert result["decision"].should_spawn is True
    assert result["decision"].reason == "tripwire_fired"
    assert result["snapshot"]["disk_percent"] == 89.0
    # The raw log line contains a real IP; the returned snapshot must be
    # the sanitized copy (ADR-0003), not the raw tail_logs output.
    assert result["snapshot"]["log_tail"]["lines"] == ["fetch failed from [REDACTED-IP]"]


def test_run_tick_suppresses_when_an_open_incident_already_exists():
    vitals_responses: dict = {}
    gh_responses: dict = {}
    _script_vitals(vitals_responses, "89", [])
    _script_incidents(gh_responses, [{"number": 1, "state": "OPEN", "createdAt": "2026-07-18T00:00:00Z"}])

    result = run_tick(_make_runner(vitals_responses), _make_runner(gh_responses), today=TODAY)

    assert result["decision"].should_spawn is False
    assert result["decision"].reason == "disarmed"
    assert result["snapshot"] is None


def test_run_tick_suppresses_when_daily_budget_exhausted():
    vitals_responses: dict = {}
    gh_responses: dict = {}
    _script_vitals(vitals_responses, "89", [])
    closed_today = [
        {"number": i, "state": "CLOSED", "createdAt": f"2026-07-18T0{i}:00:00Z"}
        for i in range(5)
    ]
    _script_incidents(gh_responses, closed_today)

    result = run_tick(_make_runner(vitals_responses), _make_runner(gh_responses), today=TODAY)

    assert result["decision"].should_spawn is False
    assert result["decision"].reason == "daily_budget_exhausted"
    assert result["snapshot"] is None


def test_run_tick_does_not_build_snapshot_when_not_spawning():
    vitals_responses: dict = {}
    gh_responses: dict = {}
    # disk_percent stays below threshold -> get_vitals is scripted, but
    # docker logs is NOT: if the snapshot were built anyway this would
    # raise AssertionError from the unscripted-command guard.
    _script_vitals(vitals_responses, "50", [("edge", True, 0)])
    _script_incidents(gh_responses, [])

    result = run_tick(_make_runner(vitals_responses), _make_runner(gh_responses), today=TODAY)

    assert result["decision"].should_spawn is False
    assert result["snapshot"] is None
