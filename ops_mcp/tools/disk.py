"""disk_breakdown: attributes a full disk to a cause — top-N `du` paths by
size plus `docker system df` totals — so the Agent can pick between the
disk-full branches (big file / superseded images / log bloat) instead of
grepping raw `du` output out of a dump."""

from __future__ import annotations

from ops_mcp.bounds import DEFAULT_TOP_N, take_top_n
from ops_mcp.command_runner import CommandRunner

DU_COMMAND = ["du", "-x", "-b", "--max-depth=2", "/"]
DOCKER_DF_COMMAND = [
    "docker", "system", "df", "--format",
    "{{.Type}}\t{{.TotalCount}}\t{{.Active}}\t{{.Size}}\t{{.Reclaimable}}",
]

_UNITS = ("B", "K", "M", "G", "T")


def _human_bytes(n: int) -> str:
    size = float(n)
    for unit in _UNITS[:-1]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}{_UNITS[-1]}"


def _parse_du(du_output: str) -> list[tuple[str, int]]:
    rows = []
    for line in du_output.splitlines():
        line = line.strip()
        if not line:
            continue
        size_str, _, path = line.partition("\t")
        if not path:
            raise ValueError(f"unexpected `du` line: {line!r}")
        rows.append((path, int(size_str)))
    rows.sort(key=lambda row: row[1], reverse=True)
    return rows


def _parse_docker_system_df(df_output: str) -> list[dict]:
    rows = []
    for line in df_output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 5:
            raise ValueError(f"unexpected `docker system df` line: {line!r}")
        type_, total, active, size, reclaimable = parts
        rows.append({
            "type": type_,
            "total": int(total),
            "active": int(active),
            "size": size,
            "reclaimable": reclaimable,
        })
    return rows


def disk_breakdown(runner: CommandRunner, top_n: int = DEFAULT_TOP_N) -> dict:
    """Return top-N disk-usage paths (biggest first) plus docker system df totals."""
    du_result = runner(DU_COMMAND)
    if not du_result.ok:
        raise RuntimeError(f"disk_breakdown: `du` failed: {du_result.stderr.strip()}")
    paths = _parse_du(du_result.stdout)
    kept_paths, dropped_paths = take_top_n(paths, top_n)

    docker_result = runner(DOCKER_DF_COMMAND)
    if not docker_result.ok:
        raise RuntimeError(
            f"disk_breakdown: `docker system df` failed: {docker_result.stderr.strip()}"
        )
    docker_rows = _parse_docker_system_df(docker_result.stdout)

    return {
        "top_paths": [
            {"path": path, "size_bytes": size, "human": _human_bytes(size)}
            for path, size in kept_paths
        ],
        "top_paths_total": len(paths),
        "top_paths_truncated": dropped_paths,
        "docker_system_df": docker_rows,
    }
