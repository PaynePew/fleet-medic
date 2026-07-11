"""command_runner: the injectable SSH/shell execution seam (CODING_STANDARDS §4)
every ops_mcp read tool depends on instead of calling subprocess directly.
"""

from __future__ import annotations

import subprocess

import pytest

from ops_mcp.command_runner import (
    CommandResult,
    local_command_runner,
    run_checked,
    ssh_command_runner,
)


def test_command_result_ok_true_on_zero_returncode():
    assert CommandResult(stdout="x", stderr="", returncode=0).ok is True


def test_command_result_ok_false_on_nonzero_returncode():
    assert CommandResult(stdout="", stderr="boom", returncode=1).ok is False


def test_local_command_runner_runs_a_real_subprocess(monkeypatch):
    captured = {}

    def fake_run(command, capture_output, text, timeout):
        captured["command"] = command
        captured["timeout"] = timeout
        return subprocess.CompletedProcess(command, returncode=0, stdout="hi\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = local_command_runner()
    result = runner(["echo", "hi"])

    assert result == CommandResult(stdout="hi\n", stderr="", returncode=0)
    assert captured["command"] == ["echo", "hi"]
    assert captured["timeout"] > 0


def test_ssh_command_runner_wraps_command_with_ssh_argv(monkeypatch):
    captured = {}

    def fake_run(command, capture_output, text, timeout):
        captured["command"] = command
        return subprocess.CompletedProcess(command, returncode=0, stdout="87%\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = ssh_command_runner(host="box.example", user="ops-ro", identity_file="/keys/ops-ro")
    result = runner(["df", "-P", "/"])

    assert result.ok
    ssh_argv = captured["command"]
    assert ssh_argv[0] == "ssh"
    assert "ops-ro@box.example" in ssh_argv
    assert "/keys/ops-ro" in ssh_argv
    assert ssh_argv[-3:] == ["df", "-P", "/"]


def test_ssh_command_runner_surfaces_nonzero_exit(monkeypatch):
    def fake_run(command, capture_output, text, timeout):
        return subprocess.CompletedProcess(command, returncode=255, stdout="", stderr="no route")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = ssh_command_runner(host="box.example", user="ops-ro", identity_file="/keys/ops-ro")
    result = runner(["df", "-P", "/"])

    assert result.ok is False
    assert result.returncode == 255
    assert "no route" in result.stderr


def test_command_result_is_frozen():
    result = CommandResult(stdout="", stderr="", returncode=0)
    with pytest.raises(AttributeError):
        result.returncode = 1


def test_run_checked_returns_result_on_success():
    runner = lambda command: CommandResult(stdout="ok", stderr="", returncode=0)  # noqa: E731
    assert run_checked(runner, ["true"], "boom").stdout == "ok"


def test_run_checked_raises_with_prefix_and_stderr_on_failure():
    runner = lambda command: CommandResult(stdout="", stderr="disk full  ", returncode=1)  # noqa: E731
    with pytest.raises(RuntimeError, match=r"^get_vitals: `df` failed: disk full$"):
        run_checked(runner, ["df"], "get_vitals: `df` failed")
