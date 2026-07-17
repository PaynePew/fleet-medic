"""decide: pure composition of the tripwire and daily budget gates into one
spawn/suppress decision. No I/O — the sensor's core "should I wake the
Agent" question is unit-testable against injected values (issue #4 AC:
"tripwire 邏輯可用注入的假量測輸出單元測試"), independent of live gh/SSH
calls. Incident dedup is not a separate check here: it is already folded
into `armed` by sensor.incidents.derive_armed_state (an open incident IS
the disarmed state), so this module only has to reason about threshold and
budget."""

from __future__ import annotations

from dataclasses import dataclass

from sensor.budget import DEFAULT_DAILY_CAP_USD, DEFAULT_PER_INCIDENT_CAP_USD, daily_budget_allows
from sensor.tripwire import DEFAULT_HIGH, DEFAULT_LOW, evaluate_tripwire


@dataclass(frozen=True)
class SensorDecision:
    should_spawn: bool
    reason: str
    tripped: bool
    armed_after: bool


def decide(
    disk_percent: float,
    *,
    armed: bool,
    incidents_spawned_today: int,
    high: float = DEFAULT_HIGH,
    low: float = DEFAULT_LOW,
    per_incident_cap_usd: float = DEFAULT_PER_INCIDENT_CAP_USD,
    daily_cap_usd: float = DEFAULT_DAILY_CAP_USD,
) -> SensorDecision:
    """One tick's full spawn/suppress decision, in priority order:
    threshold+hysteresis first, then the daily budget gate — matching the
    order a human would reason about it (is this even a trip? can we
    afford to act on it today?)."""
    tripwire = evaluate_tripwire(disk_percent, armed, high=high, low=low)

    if not tripwire.tripped:
        reason = "below_threshold" if armed else "disarmed"
        return SensorDecision(
            should_spawn=False, reason=reason, tripped=False, armed_after=tripwire.armed_after
        )

    if not daily_budget_allows(
        incidents_spawned_today,
        per_incident_cap_usd=per_incident_cap_usd,
        daily_cap_usd=daily_cap_usd,
    ):
        return SensorDecision(
            should_spawn=False,
            reason="daily_budget_exhausted",
            tripped=True,
            armed_after=tripwire.armed_after,
        )

    return SensorDecision(
        should_spawn=True, reason="tripwire_fired", tripped=True, armed_after=tripwire.armed_after
    )
