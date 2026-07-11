"""get_vitals: the same three numbers the Sensor tripwires on (df%, healthz,
restart count), re-queryable on demand for diagnosis and post-fix
Verification (CONTEXT.md)."""

from __future__ import annotations

import pytest

from ops_mcp.command_runner import CommandResult
from ops_mcp.tools.vitals import (
    DF_COMMAND,
    INSPECT_COMMAND,
    get_vitals,
)

DF_OUTPUT = (
    "Filesystem     1024-blocks     Used Available Capacity Mounted on\n"
    "/dev/sda1         20642428 17332708   2242496      89% /\n"
)


def _inspect_line(name: str, running: bool, restarts: int) -> str:
    status = "running" if running else "exited"
    return f"/{name}\t{status}\t{restarts}"


def test_get_vitals_happy_parses_disk_percent_and_services(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DF_COMMAND)] = CommandResult(stdout=DF_OUTPUT, stderr="", returncode=0)
    responses[tuple(INSPECT_COMMAND)] = CommandResult(
        stdout="\n".join([
            _inspect_line("ask-wiki-rag", True, 0),
            _inspect_line("edge", True, 2),
        ]),
        stderr="",
        returncode=0,
    )

    result = get_vitals(runner)

    assert result["disk_percent"] == 89.0
    assert result["services_total"] == 2
    assert result["services_truncated"] == 0
    names = {s["name"] for s in result["services"]}
    assert names == {"ask-wiki-rag", "edge"}


def test_get_vitals_sorts_worst_first(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DF_COMMAND)] = CommandResult(stdout=DF_OUTPUT, stderr="", returncode=0)
    responses[tuple(INSPECT_COMMAND)] = CommandResult(
        stdout="\n".join([
            _inspect_line("healthy-quiet", True, 0),
            _inspect_line("crash-looping", False, 9),
            _inspect_line("healthy-flaky", True, 3),
        ]),
        stderr="",
        returncode=0,
    )

    result = get_vitals(runner)

    ordered_names = [s["name"] for s in result["services"]]
    assert ordered_names[0] == "crash-looping"  # not running: worst
    assert ordered_names[1] == "healthy-flaky"  # running but more restarts
    assert ordered_names[2] == "healthy-quiet"


def test_get_vitals_bounds_services_to_top_n(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DF_COMMAND)] = CommandResult(stdout=DF_OUTPUT, stderr="", returncode=0)
    responses[tuple(INSPECT_COMMAND)] = CommandResult(
        stdout="\n".join(_inspect_line(f"svc-{i}", True, i) for i in range(30)),
        stderr="",
        returncode=0,
    )

    result = get_vitals(runner, top_n=20)

    assert len(result["services"]) == 20
    assert result["services_total"] == 30
    assert result["services_truncated"] == 10


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
