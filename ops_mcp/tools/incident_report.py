"""file_incident_report: closes an Incident (CONTEXT.md) as one gh issue —
the fixed five sections (偵測→假設→行動→驗證→殘留風險). Every section is
required (a missing/blank one is a tool-layer refusal, not an empty heading
left in the issue) and every section is sanitized before the issue is
created, since a public repo's Issues tab is a public-facing surface
(ADR-0003) — the same sanitizer boundary the sensor's Anomaly Snapshot
already goes through, not a second bespoke redaction (安全不外包給模型)."""

from __future__ import annotations

from ops_mcp.command_runner import CommandRunner, run_checked
from ops_mcp.sanitize import sanitize_text

# roadmap.md: "gh issue 單一去處(一事件一 issue,label 標 incident 類)". Kept
# as an independent literal (not imported from sensor.main.INCIDENT_LABEL):
# ops_mcp is the lower layer sensor already depends on, so the dependency
# must not run the other way. Phase 1 has exactly one incident type, so the
# two constants must be kept in sync by hand until a second type exists.
INCIDENT_LABEL = "incident:disk-full"

# (field name, section heading) in required, fixed order — CONTEXT.md's
# Incident Report definition.
_SECTIONS = (
    ("detection", "偵測"),
    ("hypothesis", "假設"),
    ("action", "行動"),
    ("verification", "驗證"),
    ("residual_risk", "殘留風險"),
)

_TITLE_MAX_CHARS = 80


def _require_sections(fields: dict[str, str]) -> None:
    missing = [name for name, _ in _SECTIONS if not fields[name] or not fields[name].strip()]
    if missing:
        raise ValueError(
            f"file_incident_report: missing required section(s): {', '.join(missing)}"
        )


def _build_title(detection: str, *, host: str | None) -> str:
    first_line = detection.strip().splitlines()[0]
    return f"Incident: {sanitize_text(first_line, host=host)[:_TITLE_MAX_CHARS]}"


def _build_body(fields: dict[str, str], *, run_ledger_url: str | None, host: str | None) -> str:
    sections = [
        f"## {heading}\n\n{sanitize_text(fields[name], host=host)}" for name, heading in _SECTIONS
    ]
    if run_ledger_url:
        sections.append(f"## Run Ledger\n\n{sanitize_text(run_ledger_url, host=host)}")
    return "\n\n".join(sections)


def file_incident_report(
    runner: CommandRunner,
    *,
    detection: str,
    hypothesis: str,
    action: str,
    verification: str,
    residual_risk: str,
    run_ledger_url: str | None = None,
    label: str = INCIDENT_LABEL,
    host: str | None = None,
) -> dict:
    """Open one gh issue carrying `label`, whose body is the five required
    sections in fixed order. Every field is sanitized (ADR-0003) before it
    reaches the `gh issue create` argv."""
    fields = {
        "detection": detection,
        "hypothesis": hypothesis,
        "action": action,
        "verification": verification,
        "residual_risk": residual_risk,
    }
    _require_sections(fields)

    title = _build_title(detection, host=host)
    body = _build_body(fields, run_ledger_url=run_ledger_url, host=host)

    command = ["gh", "issue", "create", "--title", title, "--body", body, "--label", label]
    result = run_checked(runner, command, "file_incident_report: `gh issue create` failed")

    return {"url": result.stdout.strip(), "label": label}
