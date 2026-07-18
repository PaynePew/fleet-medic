"""write_plan: the dry-run/confirm two-phase primitive shared by every
ops_mcp write tool (ADR-0004 Option A). A token binds a human's L2 approval
to one exact plan — not a blank check to "run whatever the tool decides
later" — so apply must reject a missing, malformed, expired, or
plan-mismatched (drifted) token instead of trusting the caller."""

from __future__ import annotations

import pytest

from ops_mcp.write_plan import (
    DEFAULT_TOKEN_TTL_SECONDS,
    ConfirmToken,
    compute_plan_digest,
    issue_confirm_token,
    verify_confirm_token,
)

PLAN = {"action": "prune_images", "candidate_ids": ["a", "b"]}
OTHER_PLAN = {"action": "prune_images", "candidate_ids": ["a", "c"]}


def test_compute_plan_digest_is_stable_regardless_of_key_order():
    assert compute_plan_digest({"a": 1, "b": 2}) == compute_plan_digest({"b": 2, "a": 1})


def test_compute_plan_digest_differs_for_different_plans():
    assert compute_plan_digest(PLAN) != compute_plan_digest(OTHER_PLAN)


def test_issue_then_verify_the_same_plan_succeeds():
    token = issue_confirm_token(PLAN, now=1_000.0)
    verify_confirm_token(token, PLAN, now=1_000.0 + 10)  # well within TTL


def test_verify_rejects_missing_token():
    with pytest.raises(ValueError, match="confirm_token"):
        verify_confirm_token(None, PLAN, now=1_000.0)
    with pytest.raises(ValueError, match="confirm_token"):
        verify_confirm_token("", PLAN, now=1_000.0)


def test_verify_rejects_malformed_token():
    with pytest.raises(ValueError, match="malformed"):
        verify_confirm_token("not-a-real-token", PLAN, now=1_000.0)


def test_verify_rejects_expired_token():
    token = issue_confirm_token(PLAN, ttl_seconds=60, now=1_000.0)
    with pytest.raises(ValueError, match="expired"):
        verify_confirm_token(token, PLAN, now=1_000.0 + 61)


def test_default_ttl_window_is_thirty_minutes():
    # Pins the #13 PAIR tuning (15 -> 30 min): a plan approved just inside the
    # window still applies; just outside is refused. Guards against an
    # accidental revert of the default that unit tests would otherwise miss.
    token = issue_confirm_token(PLAN, now=1_000.0)
    assert ConfirmToken.decode(token).expires_at == 1_000.0 + DEFAULT_TOKEN_TTL_SECONDS
    assert DEFAULT_TOKEN_TTL_SECONDS == 1800
    verify_confirm_token(token, PLAN, now=1_000.0 + 1800 - 1)  # just inside
    with pytest.raises(ValueError, match="expired"):
        verify_confirm_token(token, PLAN, now=1_000.0 + 1800 + 1)  # just outside


def test_verify_rejects_drifted_plan():
    # Box state moved between dry-run and apply (TOCTOU window ADR-0004 §3
    # names) — the token was issued for PLAN, but the freshly recomputed
    # plan at apply time is OTHER_PLAN.
    token = issue_confirm_token(PLAN, now=1_000.0)
    with pytest.raises(ValueError, match="drift"):
        verify_confirm_token(token, OTHER_PLAN, now=1_000.0 + 10)


def test_token_encode_decode_roundtrip():
    token = ConfirmToken(plan_digest="abc123", expires_at=42.5)
    assert ConfirmToken.decode(token.encode()) == token
