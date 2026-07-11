"""tail_logs: bounded log tail for one container/service — checks the
log-bloat branch of a disk-full diagnosis without a raw dump filling the
Agent's context (CLAUDE.md: 工具輸出一律有界)."""

from __future__ import annotations

from ops_mcp.command_runner import CommandRunner

MAX_TAIL_LINES = 500
DEFAULT_TAIL_LINES = 200


def tail_logs(runner: CommandRunner, service: str, lines: int = DEFAULT_TAIL_LINES) -> dict:
    """Return the last `lines` (hard-capped at MAX_TAIL_LINES) log lines for `service`."""
    if not service or not service.strip():
        raise ValueError("tail_logs: service must be a non-empty container/service name")
    bounded_lines = min(max(lines, 1), MAX_TAIL_LINES)

    result = runner(["docker", "logs", "--tail", str(bounded_lines), "--timestamps", service])
    if not result.ok:
        raise RuntimeError(f"tail_logs: `docker logs {service}` failed: {result.stderr.strip()}")

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
