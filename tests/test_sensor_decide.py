"""decide: pure composition of the tripwire and daily budget gates into one
spawn/suppress decision — no I/O, so the sensor's core "should I wake the
Agent" logic is unit-testable against injected values (issue #4 AC),
independent of live gh/SSH calls."""

from __future__ import annotations

from sensor.decide import decide


def test_below_threshold_does_not_spawn():
    result = decide(79.9, armed=True, incidents_spawned_today=0)
    assert result.should_spawn is False
    assert result.reason == "below_threshold"
    assert result.tripped is False


def test_disarmed_suppresses_even_above_high():
    result = decide(85.0, armed=False, incidents_spawned_today=0)
    assert result.should_spawn is False
    assert result.reason == "disarmed"
    assert result.tripped is False


def test_trips_and_spawns_when_armed_and_budget_ok():
    result = decide(85.0, armed=True, incidents_spawned_today=0)
    assert result.should_spawn is True
    assert result.reason == "tripwire_fired"
    assert result.tripped is True
    assert result.armed_after is False


def test_budget_exhausted_suppresses_a_tripped_reading():
    result = decide(85.0, armed=True, incidents_spawned_today=5)
    assert result.should_spawn is False
    assert result.reason == "daily_budget_exhausted"
    assert result.tripped is True  # it did trip; only the spawn is gated


def test_budget_allows_the_last_spawn_under_the_cap():
    result = decide(85.0, armed=True, incidents_spawned_today=4)
    assert result.should_spawn is True


def test_custom_thresholds_are_respected():
    result = decide(60.0, armed=True, incidents_spawned_today=0, high=50.0, low=40.0)
    assert result.should_spawn is True


def test_custom_budget_caps_are_respected():
    result = decide(
        85.0,
        armed=True,
        incidents_spawned_today=2,
        per_incident_cap_usd=2.5,
        daily_cap_usd=5.0,
    )
    assert result.should_spawn is False
    assert result.reason == "daily_budget_exhausted"
