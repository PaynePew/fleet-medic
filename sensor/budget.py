"""budget: the sensor-side daily spend gate (CLAUDE.md hard constraint —
預算三閘是確定性 code). The sensor never calls an LLM, so it can't count
real tokens; it instead caps the *count of incidents spawned today* at
daily_cap_usd / per_incident_cap_usd — the same conservative estimate the
Agent Loop's own per-incident cap (roadmap.md Open Question #3) guarantees
as a ceiling on each spawn's actual cost. Exceeding the cap doesn't error —
the caller (sensor.decide) turns a False here into a suppressed spawn with
an observable reason, which is the "放棄+報告" fallback behavior CLAUDE.md
requires of a budget gate."""

from __future__ import annotations

DEFAULT_PER_INCIDENT_CAP_USD = 1.0
DEFAULT_DAILY_CAP_USD = 5.0


def daily_budget_allows(
    incidents_spawned_today: int,
    *,
    per_incident_cap_usd: float = DEFAULT_PER_INCIDENT_CAP_USD,
    daily_cap_usd: float = DEFAULT_DAILY_CAP_USD,
) -> bool:
    """True while one more spawn today would still fit under daily_cap_usd,
    assuming each spawn costs at most per_incident_cap_usd."""
    if incidents_spawned_today < 0:
        raise ValueError(
            f"incidents_spawned_today must be >= 0, got {incidents_spawned_today}"
        )
    if per_incident_cap_usd <= 0 or daily_cap_usd <= 0:
        raise ValueError(
            "per_incident_cap_usd and daily_cap_usd must both be > 0, got "
            f"per_incident_cap_usd={per_incident_cap_usd}, daily_cap_usd={daily_cap_usd}"
        )
    max_spawns_per_day = daily_cap_usd / per_incident_cap_usd
    return incidents_spawned_today < max_spawns_per_day
