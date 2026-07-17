"""write_plan: the dry-run/confirm two-phase primitive every ops_mcp write
tool builds on (ADR-0004 Option A — L2 approval binds to one specific plan,
not to "run the agent"; arch-review 2026-07-18 #3 — token must let apply
re-verify the precondition and reject on drift, closing the dry-run→
approve→execute TOCTOU window).

A write tool's dry-run computes a *plan* (a plain dict describing exactly
what would change) and calls `issue_confirm_token` on it. Its apply
recomputes the plan from fresh box state and calls `verify_confirm_token`
*before* touching anything — a missing, malformed, expired, or
plan-mismatched token raises and nothing runs (CLAUDE.md: 安全不外包給模型,
this check is deterministic code, never a prompt instruction).

Callers should digest only a plan's *identity* fields (which targets this
touches), never fast-changing observational fields (a byte count, a
timestamp) — those would make every apply spuriously "drift" against a
dry-run that is otherwise still perfectly valid. See prune.py/rotate.py for
the per-tool projection.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass

DEFAULT_TOKEN_TTL_SECONDS = 900  # 15 minutes — Phase 1 default, not yet tuned


def compute_plan_digest(plan: dict) -> str:
    """A stable hash of `plan`, insensitive to key order — the identity a
    confirm token binds an apply call to."""
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConfirmToken:
    """The parsed shape of a confirm token: `<plan_digest>:<expires_at>`."""

    plan_digest: str
    expires_at: float

    def encode(self) -> str:
        return f"{self.plan_digest}:{self.expires_at!r}"

    @classmethod
    def decode(cls, token: str) -> ConfirmToken:
        parts = token.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"malformed confirm token: {token!r}")
        digest, expires_at_str = parts
        try:
            expires_at = float(expires_at_str)
        except ValueError as exc:
            raise ValueError(f"malformed confirm token: {token!r}") from exc
        if not digest:
            raise ValueError(f"malformed confirm token: {token!r}")
        return cls(plan_digest=digest, expires_at=expires_at)


def issue_confirm_token(
    plan: dict, *, ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS, now: float | None = None
) -> str:
    """Dry-run side: mint a token binding `plan`'s digest to a TTL window."""
    issued_at = time.time() if now is None else now
    return ConfirmToken(
        plan_digest=compute_plan_digest(plan), expires_at=issued_at + ttl_seconds
    ).encode()


def verify_confirm_token(token: str | None, plan: dict, *, now: float | None = None) -> None:
    """Apply side: raise ValueError (with a specific, actionable reason) if
    `token` does not authorize applying `plan` right now. Never returns a
    value — callers proceed only when this does not raise."""
    if not token:
        raise ValueError(
            "confirm_token is required to apply — call with dry_run=True first "
            "and pass back the confirm_token it returns"
        )
    decoded = ConfirmToken.decode(token)

    current_now = time.time() if now is None else now
    if current_now > decoded.expires_at:
        raise ValueError("confirm_token expired — re-run dry_run to get a fresh plan")

    if decoded.plan_digest != compute_plan_digest(plan):
        raise ValueError(
            "plan drift detected: box state changed since dry_run — re-run dry_run "
            "and get a fresh confirm_token before applying"
        )
