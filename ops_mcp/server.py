"""ops-mcp: MCP server wrapping the fleet-medic Tool Belt (CONTEXT.md — 分讀/
寫/報三層: this file wires all three). Claude Code (or any MCP client) mounts
this directly over stdio — see README.md for the mount command.

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
from ops_mcp.tools.incident_report import file_incident_report as _file_incident_report
from ops_mcp.tools.logs import tail_logs as _tail_logs
from ops_mcp.tools.prune import prune_images as _prune_images
from ops_mcp.tools.rotate import rotate_logs as _rotate_logs
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
def _rw_ssh_runner() -> CommandRunner:
    """Lazily build the write-capable VPS runner from env (ADR-0004 Option
    A). This is the one seam that actually enforces the L2 gate at runtime:
    `OPS_RW_SSH_KEY_PATH` only exists inside the GitHub Environment
    `box-mutations` job a human has approved (ADR-0002) — nothing wires it
    into any other job. A write tool's apply call fails closed here whenever
    that credential isn't present, same lazy-on-purpose shape as
    `_ssh_runner()` (a job without it can still list the write tools).

    The gated `.github/workflows` apply job that actually sets this env var
    is deferred (ADR-0004's closing note) to land alongside the Agent Loop
    (#6); this function is the contract that job wiring must satisfy.
    """
    host = os.environ.get("OPS_BOX_HOST")
    identity_file = os.environ.get("OPS_RW_SSH_KEY_PATH")
    user = os.environ.get("OPS_RW_SSH_USER", "ops-rw")
    missing = [
        name
        for name, value in (("OPS_BOX_HOST", host), ("OPS_RW_SSH_KEY_PATH", identity_file))
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"ops-mcp: missing env var(s) for the RW SSH runner: {', '.join(missing)}"
        )
    return ssh_command_runner(host=host, user=user, identity_file=identity_file)


@lru_cache(maxsize=1)
def _gh_runner() -> CommandRunner:
    """Local runner for `gh` — deploy history and incident issues live on
    GitHub, not the VPS."""
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


@mcp.tool()
def prune_images(dry_run: bool = True, confirm_token: str | None = None) -> dict:
    """Reclaim disk from superseded docker images (runbook disk-full Branch
    B). Two-phase: dry_run=True (the default, always call this first)
    computes which images no *running* container depends on and returns a
    confirm_token bound to that exact candidate list — it changes nothing.
    dry_run=False actually removes them and REQUIRES the confirm_token from
    a matching dry-run call; a missing, expired, or stale (box state
    changed since the dry-run) token is refused, not executed. An image
    backing a running container never enters the candidate list, and that
    check is re-verified fresh immediately before removal, not trusted from
    the dry-run."""
    runner = _ssh_runner() if dry_run else _rw_ssh_runner()
    return _prune_images(runner, dry_run=dry_run, confirm_token=confirm_token)


@mcp.tool()
def rotate_logs(service: str, dry_run: bool = True, confirm_token: str | None = None) -> dict:
    """Reclaim disk from one service's unbounded log file (runbook
    disk-full Branch C). Two-phase like prune_images: dry_run=True (the
    default, always call this first) reports the current log size for
    `service` and returns a confirm_token — it changes nothing. dry_run=False
    truncates the log file and REQUIRES that token; a missing, expired, or
    stale (log file changed since the dry-run) token is refused, not
    executed."""
    runner = _ssh_runner() if dry_run else _rw_ssh_runner()
    return _rotate_logs(runner, service, dry_run=dry_run, confirm_token=confirm_token)


@mcp.tool()
def file_incident_report(
    detection: str,
    hypothesis: str,
    action: str,
    verification: str,
    residual_risk: str,
    run_ledger_url: str | None = None,
) -> dict:
    """File the closing Incident Report for the current Incident as one gh
    issue, labeled incident:disk-full. All five sections (detection,
    hypothesis, action, verification, residual_risk) are required — call
    this only once the Incident has converged (or been abandoned), with
    every section filled in; a missing/blank section is refused rather than
    filed with a gap. Optionally attach a run_ledger_url (the workflow
    artifact link) so a human reviewer can open the full run trace. Every
    section is sanitized (IP/path/host) before the issue is created, since
    GitHub Issues on this repo is a public-facing surface."""
    host = os.environ.get("OPS_BOX_HOST")
    return _file_incident_report(
        _gh_runner(),
        detection=detection,
        hypothesis=hypothesis,
        action=action,
        verification=verification,
        residual_risk=residual_risk,
        run_ledger_url=run_ledger_url,
        host=host,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
