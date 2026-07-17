"""get_vitals: the same three numbers the Sensor tripwires on (df%, healthz,
restart count) — re-queryable on demand so the Agent can both diagnose and,
after acting, self-verify with the exact same check (CONTEXT.md: Verification;
"工具執行成功" 不是驗證).

The container query is two plain-argv steps (`docker ps -aq` then `docker
inspect ... <ids>`) rather than one `sh -c "... $(docker ps -aq)"`: the
ops-ro SSH channel forbids shell substitution and word-splits whitespace
(ADR-0003), and computing the id list here also lets a zero-container box
return cleanly instead of erroring."""

from __future__ import annotations

from dataclasses import dataclass

from ops_mcp.bounds import DEFAULT_TOP_N, take_top_n
from ops_mcp.command_runner import CommandRunner, run_checked

DF_COMMAND = ["df", "-P", "/"]
PS_IDS_COMMAND = ["docker", "ps", "-aq"]
# `::` field separator, not a TAB: a TAB in this argument would word-split in
# the ops-ro guard's `sh -c` re-parse (ADR-0003). Docker names/statuses never
# contain `::`.
INSPECT_FORMAT = "{{.Name}}::{{.State.Status}}::{{.RestartCount}}"


def inspect_command(ids: list[str]) -> list[str]:
    """`docker inspect` argv for the given container ids (no shell, no `$()`)."""
    return ["docker", "inspect", "--format", INSPECT_FORMAT, *ids]


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
        parts = line.split("::")
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
    actually matter. A box with zero containers returns an empty service list,
    not an error.
    """
    df_result = run_checked(runner, DF_COMMAND, "get_vitals: `df -P /` failed")
    disk_percent = _parse_disk_percent(df_result.stdout)

    ids_result = run_checked(runner, PS_IDS_COMMAND, "get_vitals: `docker ps -aq` failed")
    ids = ids_result.stdout.split()
    if ids:
        inspect_result = run_checked(
            runner, inspect_command(ids), "get_vitals: `docker inspect` failed"
        )
        services = _parse_services(inspect_result.stdout)
    else:
        services = []
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
