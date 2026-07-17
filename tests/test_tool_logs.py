"""tail_logs: bounded log tail for one service — checks the log-bloat branch
of a disk-full diagnosis without a raw dump filling the Agent's context."""

from __future__ import annotations

import pytest

from ops_mcp.command_runner import CommandResult
from ops_mcp.tools.logs import MAX_TAIL_LINES, tail_logs


def _log_command(service: str, lines: int) -> tuple[str, ...]:
    return ("docker", "logs", "--tail", str(lines), "--timestamps", service)


def test_tail_logs_happy_returns_requested_lines(scripted_runner):
    runner, responses = scripted_runner
    responses[_log_command("ask-wiki-rag", 3)] = CommandResult(
        stdout="line1\nline2\nline3\n", stderr="", returncode=0
    )

    result = tail_logs(runner, "ask-wiki-rag", lines=3)

    assert result["service"] == "ask-wiki-rag"
    assert result["lines"] == ["line1", "line2", "line3"]
    assert result["lines_returned"] == 3
    assert result["truncated"] is False


def test_tail_logs_rejects_empty_service():
    with pytest.raises(ValueError):
        tail_logs(lambda cmd: (_ for _ in ()).throw(AssertionError("should not run")), "  ")


def test_tail_logs_raises_clearly_on_command_failure(scripted_runner):
    runner, responses = scripted_runner
    responses[_log_command("missing-service", 200)] = CommandResult(
        stdout="", stderr="No such container: missing-service", returncode=1
    )

    with pytest.raises(RuntimeError, match="missing-service"):
        tail_logs(runner, "missing-service")


def test_tail_logs_caps_requested_lines_at_max(scripted_runner):
    runner, responses = scripted_runner
    responses[_log_command("chatty", MAX_TAIL_LINES)] = CommandResult(
        stdout="\n".join(f"l{i}" for i in range(MAX_TAIL_LINES)), stderr="", returncode=0
    )

    result = tail_logs(runner, "chatty", lines=100_000)

    assert result["lines_requested"] == 100_000
    assert result["lines_returned"] == MAX_TAIL_LINES


def test_tail_logs_defends_against_a_runner_that_ignores_tail(scripted_runner):
    # Even if the underlying command somehow returns more than asked, the
    # tool must still bound its own output (defense in depth).
    runner, responses = scripted_runner
    responses[_log_command("verbose", 5)] = CommandResult(
        stdout="\n".join(f"l{i}" for i in range(50)), stderr="", returncode=0
    )

    result = tail_logs(runner, "verbose", lines=5)

    assert result["lines_returned"] == 5
    assert result["lines"] == ["l45", "l46", "l47", "l48", "l49"]
    assert result["truncated"] is True
