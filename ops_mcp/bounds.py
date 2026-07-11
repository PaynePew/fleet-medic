"""Shared output-shaping helper: every ops_mcp read tool must return bounded
output (CLAUDE.md hard constraint) — top-N or truncated, never a raw dump,
because tool output is UX for the model, not a log file.
"""

from __future__ import annotations

DEFAULT_TOP_N = 20


def take_top_n[T](items: list[T], n: int = DEFAULT_TOP_N) -> tuple[list[T], int]:
    """Split already-sorted `items` into (kept, dropped_count) at the top-N
    boundary. Callers are responsible for sorting worst/biggest-first first —
    this only enforces the length cap."""
    if n < 0:
        raise ValueError(f"n must be >= 0, got {n}")
    return items[:n], max(0, len(items) - n)
