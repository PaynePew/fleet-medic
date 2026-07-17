"""ops-mcp: MCP server wrapping the fleet-medic Tool Belt's read layer
(CONTEXT.md — 分讀/寫/報三層,本片只做讀). Claude Code (or any MCP client)
mounts this directly over stdio — see README.md for the mount command.

Each `@mcp.tool()` docstring below IS the prompt (roadmap.md: "描述即
prompt") — a model choosing between tools never sees this file, only the
registered name + description + parameter schema.
"""

from __future__ import annotations

import os
from functools import lru_cache

from mcp.server.fastmcp import FastMCP

from ops_mcp.command_runner import CommandRunner, local_command_runner, ssh_command_runner
from ops_mcp.tools.deploys import list_recent_deploys as _list_recent_deploys
from ops_mcp.tools.disk import disk_breakdown as _disk_breakdown
from ops_mcp.tools.logs import tail_logs as _tail_logs
from ops_mcp.tools.runbook import read_runbook as _read_runbook
from ops_mcp.tools.vitals import get_vitals as _get_vitals

mcp = FastMCP("ops-mcp")


@lru_cache(maxsize=1)
def _ssh_runner() -> CommandRunner:
    """Lazily build the read-only VPS runner from env.

    Lazy on purpose: listing/mounting tools must never require credentials,
    only actually calling a VPS-bound tool does.
    """
    host = os.environ.get("OPS_BOX_HOST")
    identity_file = os.environ.get("OPS_RO_SSH_KEY_PATH")
    user = os.environ.get("OPS_RO_SSH_USER", "ops-ro")
    missing = [
        name
        for name, value in (("OPS_BOX_HOST", host), ("OPS_RO_SSH_KEY_PATH", identity_file))
        if not value
    ]
    if missing:
        raise RuntimeError(f"ops-mcp: missing env var(s) for the SSH runner: {', '.join(missing)}")
    return ssh_command_runner(host=host, user=user, identity_file=identity_file)


@lru_cache(maxsize=1)
def _gh_runner() -> CommandRunner:
    """Local runner for `gh` — deploy history lives on GitHub, not the VPS."""
    return local_command_runner()


@mcp.tool()
def get_vitals() -> dict:
    """Query the fleet box's three vitals in one call: disk_percent, and a
    worst-first, bounded list of per-container running-state + restart_count.
    Call this first to confirm an incident is real, and again after any fix
    as Verification (matching the numbers the Sensor tripwired on)."""
    return _get_vitals(_ssh_runner())


@mcp.tool()
def disk_breakdown() -> dict:
    """Attribute a full disk to a cause: top-N `du` paths by size (biggest
    first) plus `docker system df` totals for images/containers/volumes/
    build-cache. Call after get_vitals shows a high disk_percent, to pick
    which branch (big file / superseded images / log bloat) is responsible."""
    return _disk_breakdown(_ssh_runner())


@mcp.tool()
def tail_logs(service: str, lines: int = 200) -> dict:
    """Return the last `lines` (max 500) timestamped log lines for one
    container/service. Use to check whether a specific service's logs are
    the cause of a disk-full incident, or to inspect an error after a fix."""
    return _tail_logs(_ssh_runner(), service, lines)


@mcp.tool()
def list_recent_deploys(limit: int = 10) -> dict:
    """Return the `limit` (max 50) most recent GitHub Actions deploy runs
    (id/title/branch/conclusion/created_at/event), newest first. Use to test
    whether a disk-full incident correlates with a recent deploy (e.g.
    superseded image layers left behind)."""
    return _list_recent_deploys(_gh_runner(), limit)


@mcp.tool()
def read_runbook(topic: str) -> dict:
    """Read the human-authored runbook for `topic` (e.g. "disk-full") — the
    operator's prescribed diagnosis/remediation order. Read this before
    acting on a new incident type; it encodes experience live telemetry
    alone can't substitute for."""
    return _read_runbook(topic)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
