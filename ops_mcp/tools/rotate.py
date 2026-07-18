"""rotate_logs: reclaims disk from one service's unbounded log file (runbook
disk-full Branch C). Two-phase like prune_images (ADR-0004): dry_run=True
reports the current log file size and returns a confirm_token bound to that
exact target; dry_run=False requires that token, recomputes the target from
fresh box state first (rejecting on drift), and only then truncates it.
"""

from __future__ import annotations

import re

from ops_mcp.command_runner import CommandRunner, run_checked
from ops_mcp.write_plan import issue_confirm_token, verify_confirm_token

# Same boundary-input pattern as tail_logs.py: `service` crosses an ssh hop
# where the remote shell re-parses it, so it is restricted to a bare docker
# name before it reaches the seam.
_SERVICE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")

# {{.LogPath}} comes back over the SSH seam and then goes out again as a
# `du`/`truncate` argument, where the flattened argv is re-parsed by `sh -c`
# (ADR-0003). Same boundary rule as `service`: conservative charset (no
# whitespace or metacharacters), no `..` segment — and pinned to the docker
# data-root this fleet runs, because ops-rw-guard pins the same prefix: the
# two must agree, or a plan approved at dry-run time dies at the guard
# mid-apply instead of failing here, before anyone is asked to approve it.
_LOG_PATH_RE = re.compile(r"^/var/lib/docker/containers/[A-Za-z0-9._/-]+$")

_LOG_PATH_FORMAT = "{{.LogPath}}"


def log_path_command(service: str) -> list[str]:
    return ["docker", "inspect", "--format", _LOG_PATH_FORMAT, service]


def log_size_command(log_path: str) -> list[str]:
    return ["du", "-b", log_path]


def truncate_command(log_path: str) -> list[str]:
    return ["truncate", "-s", "0", log_path]


def _parse_du_size(du_output: str) -> int:
    first_line = next((ln for ln in du_output.splitlines() if ln.strip()), "")
    size_str, _, path = first_line.partition("\t")
    if not path or not size_str.isdigit():
        raise ValueError(f"unexpected `du -b` output: {du_output!r}")
    return int(size_str)


def _compute_target(runner: CommandRunner, service: str) -> dict:
    if not service or not _SERVICE_RE.match(service):
        raise ValueError(
            f"rotate_logs: service must match {_SERVICE_RE.pattern!r}, got {service!r}"
        )

    path_result = run_checked(
        runner, log_path_command(service), f"rotate_logs: `docker inspect {service}` failed"
    )
    log_path = path_result.stdout.strip()
    if not log_path:
        raise RuntimeError(f"rotate_logs: empty LogPath for service={service!r}")
    if not _LOG_PATH_RE.match(log_path) or ".." in log_path.split("/"):
        raise RuntimeError(
            f"rotate_logs: suspicious LogPath for service={service!r}, "
            f"refusing to use it as command argv: {log_path!r}"
        )

    size_result = run_checked(
        runner, log_size_command(log_path), f"rotate_logs: `du -b {log_path}` failed"
    )
    reclaim_bytes = _parse_du_size(size_result.stdout)

    return {"service": service, "log_path": log_path, "reclaim_bytes": reclaim_bytes}


def _plan_key(target: dict) -> dict:
    # Digest only *which log file* would be truncated — never its byte size,
    # which keeps changing while a human reviews the dry-run and would make
    # apply spuriously "drift" against an otherwise-still-valid plan.
    return {"action": "rotate_logs", "service": target["service"], "log_path": target["log_path"]}


def rotate_logs(
    runner: CommandRunner,
    service: str,
    *,
    dry_run: bool,
    confirm_token: str | None = None,
    now: float | None = None,
) -> dict:
    """Two-phase log rotation. `dry_run=True` (default caller mode) only
    reads box state — see module docstring for the phase contract."""
    target = _compute_target(runner, service)
    plan_key = _plan_key(target)

    if dry_run:
        token = issue_confirm_token(plan_key, now=now)
        return {"dry_run": True, "confirm_token": token, **target}

    verify_confirm_token(confirm_token, plan_key, now=now)

    run_checked(
        runner,
        truncate_command(target["log_path"]),
        f"rotate_logs: truncate failed for service={service!r}",
    )
    return {"dry_run": False, "rotated": True, **target}
