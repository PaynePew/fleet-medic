"""snapshot: assembles the Anomaly Snapshot (CONTEXT.md — the sole
sensor->agent handoff) from the same read tools the Agent itself calls
later for Verification (get_vitals, tail_logs), so the numbers Diagnosis
starts from and the numbers that prove a fix worked come from one code
path (issue #4 build brief: 用既有讀工具取三數字/快照,別重寫 SSH)."""

from __future__ import annotations

from ops_mcp.command_runner import CommandRunner
from ops_mcp.tools.logs import DEFAULT_TAIL_LINES, tail_logs
from ops_mcp.tools.vitals import get_vitals


def build_anomaly_snapshot(
    runner: CommandRunner, *, vitals: dict | None = None, log_lines: int = DEFAULT_TAIL_LINES
) -> dict:
    """disk_percent + the worst-first service table (get_vitals) plus a
    bounded log tail (tail_logs, already bounded — CLAUDE.md: 工具輸出一律
    有界) for the single worst service, if any are running. Pass an
    already-fetched `vitals` dict to avoid a second SSH round trip when the
    caller queried it a moment earlier to decide whether to spawn at all.

    A box with zero containers gets log_tail=None instead of a call with
    nothing to tail.
    """
    if vitals is None:
        vitals = get_vitals(runner)

    log_tail = None
    if vitals["services"]:
        worst_service = vitals["services"][0]["name"]
        try:
            log_tail = tail_logs(runner, worst_service, lines=log_lines)
        except RuntimeError as exc:
            # A service can be too broken to even fetch logs from (e.g. the
            # container was just removed) — that is itself diagnostic
            # signal for the Agent, not a reason to lose the rest of the
            # snapshot (CODING_STANDARDS §3: don't swallow, record).
            log_tail = {"service": worst_service, "error": str(exc)}

    return {
        "disk_percent": vitals["disk_percent"],
        "services": vitals["services"],
        "services_total": vitals["services_total"],
        "services_truncated": vitals["services_truncated"],
        "log_tail": log_tail,
    }
