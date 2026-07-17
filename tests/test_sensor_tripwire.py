"""tripwire: the deterministic df% threshold that wakes the Agent
(ADR-0001). A Schmitt trigger (trip above `high`, rearm only below `low`)
stops a reading that oscillates around the line from re-tripping every
tick (roadmap.md arch-review #5: 遲滯/防門檻震盪)."""

from __future__ import annotations

import pytest

from sensor.tripwire import evaluate_tripwire


def test_79_9_percent_does_not_trip_while_armed():
    result = evaluate_tripwire(79.9, armed=True)
    assert result.tripped is False
    assert result.armed_after is True


def test_80_1_percent_trips_and_disarms():
    result = evaluate_tripwire(80.1, armed=True)
    assert result.tripped is True
    assert result.armed_after is False


def test_exactly_high_does_not_trip():
    # Boundary is strictly-greater-than, not >=.
    result = evaluate_tripwire(80.0, armed=True)
    assert result.tripped is False
    assert result.armed_after is True


def test_stays_disarmed_in_the_dead_zone():
    # Between low and high, a disarmed sensor stays disarmed — this is the
    # hysteresis: closing back in on the line from above must not re-trip.
    result = evaluate_tripwire(78.0, armed=False)
    assert result.tripped is False
    assert result.armed_after is False


def test_rearms_once_below_low():
    result = evaluate_tripwire(74.9, armed=False)
    assert result.tripped is False  # rearming alone is not a trip
    assert result.armed_after is True


def test_exactly_low_does_not_rearm():
    # Boundary is strictly-less-than, not <=.
    result = evaluate_tripwire(75.0, armed=False)
    assert result.armed_after is False


def test_disarmed_never_trips_even_far_above_high():
    result = evaluate_tripwire(99.0, armed=False)
    assert result.tripped is False
    assert result.armed_after is False


def test_full_flap_cycle_needs_a_confirmed_recovery_before_retripping():
    first = evaluate_tripwire(81.0, armed=True)
    assert first.tripped is True and first.armed_after is False

    still_high = evaluate_tripwire(79.0, armed=first.armed_after)
    assert still_high.tripped is False and still_high.armed_after is False

    recovered = evaluate_tripwire(74.0, armed=still_high.armed_after)
    assert recovered.tripped is False and recovered.armed_after is True

    second = evaluate_tripwire(81.0, armed=recovered.armed_after)
    assert second.tripped is True and second.armed_after is False


def test_rejects_low_greater_than_or_equal_to_high():
    with pytest.raises(ValueError):
        evaluate_tripwire(90.0, armed=True, high=75.0, low=80.0)
