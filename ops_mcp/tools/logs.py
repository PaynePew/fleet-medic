"""tail_logs: bounded log tail for one container/service — checks the
log-bloat branch of a disk-full diagnosis without a raw dump filling the
Agent's context (CLAUDE.md: 工具輸出一律有界)."""

from __future__ import annotations

import re

from ops_mcp.command_runner import CommandRunner, run_checked

# `service` is boundary input from the LLM and the command crosses an ssh hop
# where the remote shell re-parses it, so it is restricted to a bare docker
# name before it reaches the seam — no shell metachars, no leading dash that
# `docker logs` would parse as an option (same pattern as runbook.py's topic).
_SERVICE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
MAX_TAIL_LINES = 500
DEFAULT_TAIL_LINES = 200


def tail_logs(runner: CommandRunner, service: str, lines: int = DEFAULT_TAIL_LINES) -> dict:
    """Return the last `lines` (hard-capped at MAX_TAIL_LINES) log lines for `service`."""
    if not service or not _SERVICE_RE.match(service):
        raise ValueError(
            f"tail_logs: service must match {_SERVICE_RE.pattern!r}, got {service!r}"
        )
    bounded_lines = min(max(lines, 1), MAX_TAIL_LINES)

    command = ["docker", "logs", "--tail", str(bounded_lines), "--timestamps", service]
    result = run_checked(runner, command, f"tail_logs: `docker logs {service}` failed")

    all_lines = result.stdout.splitlines()
    # Defense in depth: re-truncate even if the underlying command returned more.
    bounded_output = all_lines[-bounded_lines:]

    return {
        "service": service,
        "lines_requested": lines,
        "lines_returned": len(bounded_output),
        "lines": bounded_output,
        "truncated": len(all_lines) > len(bounded_output),
    }
