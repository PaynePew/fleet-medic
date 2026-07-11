"""bounds: the shared top-N cap every ops_mcp read tool applies to whatever it
returns (CLAUDE.md hard constraint: 工具輸出一律有界)."""

from __future__ import annotations

import pytest

from ops_mcp.bounds import DEFAULT_TOP_N, take_top_n


def test_take_top_n_keeps_everything_under_the_cap():
    kept, dropped = take_top_n([1, 2, 3], n=10)
    assert kept == [1, 2, 3]
    assert dropped == 0


def test_take_top_n_truncates_and_reports_dropped_count():
    items = list(range(30))
    kept, dropped = take_top_n(items, n=20)
    assert kept == items[:20]
    assert dropped == 10


def test_take_top_n_default_cap_is_twenty():
    kept, dropped = take_top_n(list(range(25)))
    assert len(kept) == DEFAULT_TOP_N == 20
    assert dropped == 5


def test_take_top_n_rejects_negative_n():
    with pytest.raises(ValueError):
        take_top_n([1, 2], n=-1)
