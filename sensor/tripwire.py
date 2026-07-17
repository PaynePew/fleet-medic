"""tripwire: the deterministic df% threshold that wakes the Agent
(ADR-0001 — LLM never enters this decision). A plain `df > 80` would flap
on every tick that oscillates around the line, filing a fresh incident
each time; a Schmitt trigger (trip above `high`, rearm only once the
reading falls below a lower `low`) is the standard fix (roadmap.md
arch-review #5: 遲滯/防門檻震盪)."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_HIGH = 80.0
DEFAULT_LOW = 75.0


@dataclass(frozen=True)
class TripwireResult:
    tripped: bool
    armed_after: bool


def evaluate_tripwire(
    disk_percent: float,
    armed: bool,
    *,
    high: float = DEFAULT_HIGH,
    low: float = DEFAULT_LOW,
) -> TripwireResult:
    """Trip only while armed and disk_percent > high; rearm only once
    disk_percent drops below low. Between low and high the armed bit is
    unchanged — that dead zone is what stops threshold noise from flapping.
    Rearming alone never trips (armed_after can flip True without
    tripped=True): a reading has to cross high again on a later call.
    """
    if low >= high:
        raise ValueError(f"low ({low}) must be < high ({high})")

    if armed and disk_percent > high:
        return TripwireResult(tripped=True, armed_after=False)
    if not armed and disk_percent < low:
        return TripwireResult(tripped=False, armed_after=True)
    return TripwireResult(tripped=False, armed_after=armed)
