"""budget: the sensor-side daily spend gate (CLAUDE.md hard constraint —
預算三閘是確定性 code). The sensor never calls an LLM, so instead of
counting tokens it caps the number of incidents spawned today at
daily_cap_usd / per_incident_cap_usd — the same conservative ceiling the
Agent Loop's own per-incident cap guarantees on each spawn's actual cost
(roadmap.md Open Question #3)."""

from __future__ import annotations

import pytest

from sensor.budget import daily_budget_allows


def test_allows_when_under_the_default_cap():
    # $5 daily / $1 per-incident -> 5 spawns/day; the 5th (index 4) is
    # still allowed.
    assert daily_budget_allows(4) is True


def test_blocks_at_the_default_cap():
    assert daily_budget_allows(5) is False


def test_allows_the_first_spawn_of_the_day():
    assert daily_budget_allows(0) is True


def test_respects_custom_caps():
    assert daily_budget_allows(1, per_incident_cap_usd=2.5, daily_cap_usd=5.0) is True
    assert daily_budget_allows(2, per_incident_cap_usd=2.5, daily_cap_usd=5.0) is False


def test_rejects_negative_spawn_count():
    with pytest.raises(ValueError):
        daily_budget_allows(-1)


def test_rejects_nonpositive_caps():
    with pytest.raises(ValueError):
        daily_budget_allows(0, per_incident_cap_usd=0.0)
    with pytest.raises(ValueError):
        daily_budget_allows(0, daily_cap_usd=0.0)
