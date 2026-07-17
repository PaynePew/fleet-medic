"""get_vitals: the same three numbers the Sensor tripwires on (df%, healthz,
restart count), re-queryable on demand for diagnosis and post-fix
Verification (CONTEXT.md)."""

from __future__ import annotations

import pytest

from ops_mcp.command_runner import CommandResult
from ops_mcp.tools.vitals import (
    DF_COMMAND,
    PS_IDS_COMMAND,
    get_vitals,
    inspect_command,
)

DF_OUTPUT = (
    "Filesystem     1024-blocks     Used Available Capacity Mounted on\n"
    "/dev/sda1         20642428 17332708   2242496      89% /\n"
)


def _inspect_line(name: str, running: bool, restarts: int) -> str:
    status = "running" if running else "exited"
    return f"/{name}::{status}::{restarts}"


def _script_containers(responses, services: list[tuple[str, bool, int]]) -> None:
    """Script `docker ps -aq` + the matching `docker inspect` for `services`."""
    ids = [f"id{i}" for i in range(len(services))]
    responses[tuple(PS_IDS_COMMAND)] = CommandResult(
        stdout=("\n".join(ids) + "\n" if ids else ""), stderr="", returncode=0
    )
    if ids:
        responses[tuple(inspect_command(ids))] = CommandResult(
            stdout="\n".join(_inspect_line(n, r, c) for n, r, c in services),
            stderr="",
            returncode=0,
        )


def test_get_vitals_happy_parses_disk_percent_and_services(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DF_COMMAND)] = CommandResult(stdout=DF_OUTPUT, stderr="", returncode=0)
    _script_containers(responses, [("ask-wiki-rag", True, 0), ("edge", True, 2)])

    result = get_vitals(runner)

    assert result["disk_percent"] == 89.0
    assert result["services_total"] == 2
    assert result["services_truncated"] == 0
    names = {s["name"] for s in result["services"]}
    assert names == {"ask-wiki-rag", "edge"}


def test_get_vitals_sorts_worst_first(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DF_COMMAND)] = CommandResult(stdout=DF_OUTPUT, stderr="", returncode=0)
    _script_containers(responses, [
        ("healthy-quiet", True, 0),
        ("crash-looping", False, 9),
        ("healthy-flaky", True, 3),
    ])

    result = get_vitals(runner)

    ordered_names = [s["name"] for s in result["services"]]
    assert ordered_names[0] == "crash-looping"  # not running: worst
    assert ordered_names[1] == "healthy-flaky"  # running but more restarts
    assert ordered_names[2] == "healthy-quiet"


def test_get_vitals_bounds_services_to_top_n(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DF_COMMAND)] = CommandResult(stdout=DF_OUTPUT, stderr="", returncode=0)
    _script_containers(responses, [(f"svc-{i}", True, i) for i in range(30)])

    result = get_vitals(runner, top_n=20)

    assert len(result["services"]) == 20
    assert result["services_total"] == 30
    assert result["services_truncated"] == 10


def test_get_vitals_returns_empty_services_on_zero_container_box(scripted_runner):
    # `docker ps -aq` empty → skip inspect entirely (not scripted, so calling
    # it would fail the test) and return disk% with an empty service list.
    runner, responses = scripted_runner
    responses[tuple(DF_COMMAND)] = CommandResult(stdout=DF_OUTPUT, stderr="", returncode=0)
    _script_containers(responses, [])

    result = get_vitals(runner)

    assert result["disk_percent"] == 89.0
    assert result["services"] == []
    assert result["services_total"] == 0
    assert result["services_truncated"] == 0


def test_get_vitals_raises_clearly_when_df_fails(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DF_COMMAND)] = CommandResult(stdout="", stderr="df: /: no such device", returncode=1)

    with pytest.raises(RuntimeError, match="df"):
        get_vitals(runner)


def test_get_vitals_raises_on_malformed_df_output(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DF_COMMAND)] = CommandResult(stdout="not df output", stderr="", returncode=0)

    with pytest.raises(ValueError):
        get_vitals(runner)
