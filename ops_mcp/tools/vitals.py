"""get_vitals: the same three numbers the Sensor tripwires on (df%, healthz,
restart count) — re-queryable on demand so the Agent can both diagnose and,
after acting, self-verify with the exact same check (CONTEXT.md: Verification;
"工具執行成功" 不是驗證)."""

from __future__ import annotations

from dataclasses import dataclass

from ops_mcp.bounds import DEFAULT_TOP_N, take_top_n
from ops_mcp.command_runner import CommandRunner

DF_COMMAND = ["df", "-P", "/"]
INSPECT_COMMAND = [
    "sh", "-c",
    "docker inspect --format '{{.Name}}\t{{.State.Status}}\t{{.RestartCount}}' $(docker ps -aq)",
]


@dataclass(frozen=True)
class _ServiceVital:
    name: str
    running: bool
    restart_count: int


def _parse_disk_percent(df_output: str) -> float:
    lines = [ln for ln in df_output.splitlines() if ln.strip()]
    fields = lines[-1].split() if lines else []
    if len(fields) < 5 or not fields[4].endswith("%"):
        raise ValueError(f"unexpected `df -P /` output: {df_output!r}")
    return float(fields[4].rstrip("%"))


def _parse_services(inspect_output: str) -> list[_ServiceVital]:
    services = []
    for line in inspect_output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise ValueError(f"unexpected `docker inspect` line: {line!r}")
        name, status, restart_count = parts
        services.append(
            _ServiceVital(
                name=name.lstrip("/"),
                running=(status == "running"),
                restart_count=int(restart_count),
            )
        )
    return services


def get_vitals(runner: CommandRunner, top_n: int = DEFAULT_TOP_N) -> dict:
    """Query disk%, per-service run state, and restart counts in one call.

    Services are sorted worst-first (stopped before running, then by restart
    count descending) so a truncated top-N never hides the containers that
    actually matter.
    """
    df_result = runner(DF_COMMAND)
    if not df_result.ok:
        raise RuntimeError(f"get_vitals: `df -P /` failed: {df_result.stderr.strip()}")
    disk_percent = _parse_disk_percent(df_result.stdout)

    inspect_result = runner(INSPECT_COMMAND)
    if not inspect_result.ok:
        raise RuntimeError(f"get_vitals: docker inspect failed: {inspect_result.stderr.strip()}")
    services = _parse_services(inspect_result.stdout)
    services.sort(key=lambda s: (s.running, -s.restart_count, s.name))

    kept, dropped = take_top_n(services, top_n)
    return {
        "disk_percent": disk_percent,
        "services": [
            {"name": s.name, "running": s.running, "restart_count": s.restart_count}
            for s in kept
        ],
        "services_total": len(services),
        "services_truncated": dropped,
    }
