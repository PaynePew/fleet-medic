"""snapshot: assembles the Anomaly Snapshot (CONTEXT.md) — the sole
sensor->agent handoff — from the same read tools the Agent later calls for
Verification (get_vitals, tail_logs), so diagnosis and post-fix checks
share one code path (issue #4 build brief: 用既有讀工具,別重寫 SSH)."""

from __future__ import annotations

import pytest

from ops_mcp.command_runner import CommandResult
from ops_mcp.tools.vitals import DF_COMMAND, PS_IDS_COMMAND, inspect_command
from sensor.snapshot import build_anomaly_snapshot

DF_OUTPUT = (
    "Filesystem     1024-blocks     Used Available Capacity Mounted on\n"
    "/dev/sda1         20642428 17332708   2242496      89% /\n"
)


def _script_vitals(responses, services: list[tuple[str, bool, int]]) -> None:
    ids = [f"id{i}" for i in range(len(services))]
    responses[tuple(DF_COMMAND)] = CommandResult(stdout=DF_OUTPUT, stderr="", returncode=0)
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


def _log_command(service: str, lines: int) -> tuple[str, ...]:
    return ("docker", "logs", "--tail", str(lines), "--timestamps", service)


def test_build_snapshot_happy_includes_log_tail_for_worst_service(scripted_runner):
    runner, responses = scripted_runner
    _script_vitals(responses, [("crash-looping", False, 9), ("edge", True, 0)])
    responses[_log_command("crash-looping", 200)] = CommandResult(
        stdout="oom\nrestarting\n", stderr="", returncode=0
    )

    snapshot = build_anomaly_snapshot(runner)

    assert snapshot["disk_percent"] == 89.0
    assert snapshot["services_total"] == 2
    assert snapshot["log_tail"]["service"] == "crash-looping"
    assert snapshot["log_tail"]["lines"] == ["oom", "restarting"]


def test_build_snapshot_skips_log_tail_when_zero_containers(scripted_runner):
    runner, responses = scripted_runner
    _script_vitals(responses, [])
    # No `docker logs` scripted: if the snapshot builder called it anyway,
    # scripted_runner would raise AssertionError and fail this test.

    snapshot = build_anomaly_snapshot(runner)

    assert snapshot["services"] == []
    assert snapshot["log_tail"] is None


def test_build_snapshot_records_log_tail_error_without_raising(scripted_runner):
    runner, responses = scripted_runner
    _script_vitals(responses, [("flaky", True, 1)])
    responses[_log_command("flaky", 200)] = CommandResult(
        stdout="", stderr="No such container: flaky", returncode=1
    )

    snapshot = build_anomaly_snapshot(runner)

    assert snapshot["log_tail"]["service"] == "flaky"
    assert "flaky" in snapshot["log_tail"]["error"]


def test_build_snapshot_propagates_vitals_failure(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DF_COMMAND)] = CommandResult(
        stdout="", stderr="df: /: no such device", returncode=1
    )

    with pytest.raises(RuntimeError, match="df"):
        build_anomaly_snapshot(runner)


def test_build_snapshot_reuses_prefetched_vitals_without_recalling_get_vitals(scripted_runner):
    runner, responses = scripted_runner
    # Only `docker logs` is scripted: df/ps/inspect are deliberately absent,
    # so a redundant get_vitals() call inside build_anomaly_snapshot would
    # fail this test via scripted_runner's unscripted-command assertion.
    responses[_log_command("edge", 200)] = CommandResult(stdout="l1\n", stderr="", returncode=0)
    prefetched_vitals = {
        "disk_percent": 91.0,
        "services": [{"name": "edge", "running": True, "restart_count": 0}],
        "services_total": 1,
        "services_truncated": 0,
    }

    snapshot = build_anomaly_snapshot(runner, vitals=prefetched_vitals)

    assert snapshot["disk_percent"] == 91.0
    assert snapshot["log_tail"]["lines"] == ["l1"]
