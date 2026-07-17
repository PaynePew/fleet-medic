"""main: the sensor's Actions entrypoint. `run_tick` is the testable core —
its only I/O is through the two injected CommandRunners (issue #4 AC); the
thin `main()` below wires real env vars and files around it for
`.github/workflows/sensor.yml` and is deliberately not unit tested, the
same convention ops_mcp/server.py's own `main()` follows.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

from ops_mcp.command_runner import CommandRunner, local_command_runner, ssh_command_runner
from ops_mcp.sanitize import sanitize_value
from ops_mcp.tools.vitals import get_vitals
from sensor.decide import DEFAULT_DAILY_CAP_USD, DEFAULT_PER_INCIDENT_CAP_USD, decide
from sensor.incidents import count_created_on, derive_armed_state, list_incidents
from sensor.snapshot import build_anomaly_snapshot
from sensor.tripwire import DEFAULT_HIGH, DEFAULT_LOW

# roadmap.md: "gh issue 單一去處(一事件一 issue,label 標 incident 類)" —
# Phase 1's only incident type is disk-full, so this is a fixed constant
# rather than a parameter threaded through the whole call chain.
INCIDENT_LABEL = "incident:disk-full"


def run_tick(
    vitals_runner: CommandRunner,
    gh_runner: CommandRunner,
    *,
    incident_label: str = INCIDENT_LABEL,
    today: date,
    host: str | None = None,
    high: float = DEFAULT_HIGH,
    low: float = DEFAULT_LOW,
    per_incident_cap_usd: float = DEFAULT_PER_INCIDENT_CAP_USD,
    daily_cap_usd: float = DEFAULT_DAILY_CAP_USD,
    log_lines: int = 200,
) -> dict:
    """One sensor tick: read vitals, derive armed state + today's spawn
    count from gh issue history, decide, and — only when spawning — build
    and sanitize the Anomaly Snapshot (never build it, and never pay for
    the extra SSH round trip, on a tick that isn't handing off).
    """
    vitals = get_vitals(vitals_runner)
    disk_percent = vitals["disk_percent"]

    issues = list_incidents(gh_runner, incident_label)
    armed = derive_armed_state(issues)
    incidents_spawned_today = count_created_on(issues, today)

    decision = decide(
        disk_percent,
        armed=armed,
        incidents_spawned_today=incidents_spawned_today,
        high=high,
        low=low,
        per_incident_cap_usd=per_incident_cap_usd,
        daily_cap_usd=daily_cap_usd,
    )

    snapshot = None
    if decision.should_spawn:
        raw_snapshot = build_anomaly_snapshot(vitals_runner, vitals=vitals, log_lines=log_lines)
        snapshot = sanitize_value(raw_snapshot, host=host)

    return {
        "decision": decision,
        "disk_percent": disk_percent,
        "incidents_spawned_today": incidents_spawned_today,
        "snapshot": snapshot,
    }


def main() -> None:
    host = os.environ.get("OPS_BOX_HOST")
    identity_file = os.environ.get("OPS_RO_SSH_KEY_PATH")
    user = os.environ.get("OPS_RO_SSH_USER", "ops-ro")
    missing = [
        name
        for name, value in (("OPS_BOX_HOST", host), ("OPS_RO_SSH_KEY_PATH", identity_file))
        if not value
    ]
    if missing:
        raise RuntimeError(f"sensor.main: missing env var(s): {', '.join(missing)}")

    vitals_runner = ssh_command_runner(host=host, user=user, identity_file=identity_file)
    gh_runner = local_command_runner()

    result = run_tick(vitals_runner, gh_runner, today=datetime.now(UTC).date(), host=host)
    decision = result["decision"]

    _write_github_output("should_spawn", "true" if decision.should_spawn else "false")
    _write_github_output("reason", decision.reason)
    _write_step_summary(result)

    if result["snapshot"] is not None:
        snapshot_path = Path(os.environ.get("SNAPSHOT_PATH", "anomaly-snapshot.json"))
        snapshot_path.write_text(json.dumps(result["snapshot"], indent=2), encoding="utf-8")

    print(
        f"sensor: disk_percent={result['disk_percent']} decision={decision.reason} "
        f"should_spawn={decision.should_spawn}"
    )


def _write_github_output(key: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{key}={value}\n")


def _write_step_summary(result: dict) -> None:
    # The daily-budget-exhausted case in particular needs an observable
    # record even though nothing gets spawned (CLAUDE.md: 留下可觀測記錄);
    # the step summary is public (ADR-0003) but this text is already just
    # numbers/reason strings, never raw box output.
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    decision = result["decision"]
    lines = [
        "### fleet-medic sensor tick",
        f"- disk_percent: {result['disk_percent']}",
        f"- decision: {decision.reason} (should_spawn={decision.should_spawn})",
        f"- incidents_spawned_today: {result['incidents_spawned_today']}",
    ]
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
