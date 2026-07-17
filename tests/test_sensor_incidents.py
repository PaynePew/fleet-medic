"""incidents: sensor-side gh issue queries. GitHub Issues are the sensor's
only durable store across stateless Actions runs (roadmap.md arch-review
#5: "Actions 無狀態,issue 即狀態儲存") — dedup, the daily budget count, and
the tripwire's armed/disarmed state are all derived from one `gh issue
list` call."""

from __future__ import annotations

import json
from datetime import date

import pytest

from ops_mcp.command_runner import CommandResult
from sensor.incidents import (
    MAX_LIST_LIMIT,
    count_created_on,
    derive_armed_state,
    has_open_incident,
    list_incidents,
)


def _issue(number: int, state: str, created_at: str) -> dict:
    return {"number": number, "state": state, "createdAt": created_at}


def _gh_command(label: str, limit: int) -> tuple[str, ...]:
    return (
        "gh", "issue", "list", "--state", "all", "--label", label,
        "--json", "number,state,createdAt", "--limit", str(limit),
    )


# --- list_incidents (I/O) -----------------------------------------------


def test_list_incidents_happy_parses_issues(scripted_runner):
    runner, responses = scripted_runner
    issues = [_issue(1, "OPEN", "2026-07-18T09:00:00Z")]
    responses[_gh_command("incident:disk-full", 100)] = CommandResult(
        stdout=json.dumps(issues), stderr="", returncode=0
    )

    result = list_incidents(runner, "incident:disk-full")

    assert result == issues


def test_list_incidents_bounds_limit_at_max(scripted_runner):
    runner, responses = scripted_runner
    responses[_gh_command("incident:disk-full", MAX_LIST_LIMIT)] = CommandResult(
        stdout="[]", stderr="", returncode=0
    )

    result = list_incidents(runner, "incident:disk-full", limit=10_000)

    assert result == []


def test_list_incidents_raises_clearly_on_command_failure(scripted_runner):
    runner, responses = scripted_runner
    responses[_gh_command("incident:disk-full", 100)] = CommandResult(
        stdout="", stderr="gh: not authenticated", returncode=1
    )

    with pytest.raises(RuntimeError, match="gh issue list"):
        list_incidents(runner, "incident:disk-full")


def test_list_incidents_raises_on_malformed_json(scripted_runner):
    runner, responses = scripted_runner
    responses[_gh_command("incident:disk-full", 100)] = CommandResult(
        stdout="not json", stderr="", returncode=0
    )

    with pytest.raises(ValueError):
        list_incidents(runner, "incident:disk-full")


# --- has_open_incident (pure) --------------------------------------------


def test_has_open_incident_true_when_any_open():
    issues = [_issue(1, "CLOSED", "2026-07-17T00:00:00Z"), _issue(2, "OPEN", "2026-07-18T00:00:00Z")]
    assert has_open_incident(issues) is True


def test_has_open_incident_false_when_all_closed():
    issues = [_issue(1, "CLOSED", "2026-07-17T00:00:00Z")]
    assert has_open_incident(issues) is False


def test_has_open_incident_false_when_empty():
    assert has_open_incident([]) is False


# --- count_created_on (pure) ----------------------------------------------


def test_count_created_on_matches_day_prefix():
    issues = [
        _issue(1, "CLOSED", "2026-07-18T09:00:00Z"),
        _issue(2, "OPEN", "2026-07-18T23:59:00Z"),
        _issue(3, "CLOSED", "2026-07-17T09:00:00Z"),
    ]
    assert count_created_on(issues, date(2026, 7, 18)) == 2


def test_count_created_on_zero_when_none_match():
    issues = [_issue(1, "CLOSED", "2026-07-17T09:00:00Z")]
    assert count_created_on(issues, date(2026, 7, 18)) == 0


# --- derive_armed_state (pure) --------------------------------------------


def test_derive_armed_state_disarmed_when_open_incident_exists():
    issues = [_issue(1, "OPEN", "2026-07-18T00:00:00Z")]
    assert derive_armed_state(issues) is False


def test_derive_armed_state_armed_when_no_incidents_ever():
    assert derive_armed_state([]) is True


def test_derive_armed_state_armed_once_the_only_incident_is_closed():
    issues = [_issue(1, "CLOSED", "2026-07-17T00:00:00Z")]
    assert derive_armed_state(issues) is True


def test_derive_armed_state_disarmed_when_any_incident_among_several_is_open():
    issues = [
        _issue(1, "CLOSED", "2026-07-17T00:00:00Z"),
        _issue(2, "OPEN", "2026-07-18T00:00:00Z"),
    ]
    assert derive_armed_state(issues) is False
