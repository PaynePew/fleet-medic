"""sanitize: the shared public-output boundary (ADR-0003) — every tool
output that leaves the box and enters a public surface (Actions log,
artifact, Run Ledger) must pass through this before it's printed, uploaded,
or embedded anywhere the public web can read it."""

from __future__ import annotations

import pytest

from ops_mcp.sanitize import sanitize_text, sanitize_value


def test_sanitize_text_redacts_ipv4_addresses():
    text = "connection refused from 10.20.30.40 on retry"
    assert sanitize_text(text) == "connection refused from [REDACTED-IP] on retry"


def test_sanitize_text_redacts_multiple_ips():
    text = "192.168.1.1 -> 8.8.8.8"
    assert sanitize_text(text) == "[REDACTED-IP] -> [REDACTED-IP]"


def test_sanitize_text_redacts_home_username():
    text = "du: cannot read /home/maxl/uploads/tmp.bin"
    assert sanitize_text(text) == "du: cannot read /home/[REDACTED-USER]/uploads/tmp.bin"


def test_sanitize_text_redacts_exact_host_string_when_given():
    text = "ssh: connect to host box.example.com port 22: timed out"
    assert sanitize_text(text, host="box.example.com") == (
        "ssh: connect to host [REDACTED-HOST] port 22: timed out"
    )


def test_sanitize_text_noop_when_nothing_to_redact():
    text = "disk_percent=87.0 services=3"
    assert sanitize_text(text) == text


def test_sanitize_text_noop_without_host_argument():
    # No host given -> host-shaped substrings in the text are left alone;
    # only IP/home-user patterns are redacted unconditionally.
    text = "deployed to prod-box-1"
    assert sanitize_text(text) == text


def test_sanitize_value_recurses_through_dict_and_list():
    value = {
        "log_tail": {
            "lines": ["fetch from 10.0.0.5 failed", "path /home/maxl/data missing"],
        },
        "top_paths": [{"path": "/home/maxl/uploads", "size_bytes": 100}],
    }

    result = sanitize_value(value)

    assert result["log_tail"]["lines"][0] == "fetch from [REDACTED-IP] failed"
    assert result["log_tail"]["lines"][1] == "path /home/[REDACTED-USER]/data missing"
    assert result["top_paths"][0]["path"] == "/home/[REDACTED-USER]/uploads"
    assert result["top_paths"][0]["size_bytes"] == 100  # int untouched


def test_sanitize_value_passes_through_non_string_scalars():
    value = {"disk_percent": 87.5, "running": True, "restart_count": 0, "note": None}

    result = sanitize_value(value)

    assert result == value


def test_sanitize_value_applies_host_recursively():
    value = {"services": [{"name": "edge", "detail": "on box.example.com now"}]}

    result = sanitize_value(value, host="box.example.com")

    assert result["services"][0]["detail"] == "on [REDACTED-HOST] now"


def test_sanitize_value_raises_on_unsupported_type():
    # A failure path is a hard requirement here (ADR-0003 / CODING_STANDARDS
    # §1): failing open on an unknown structural type would let unsanitized
    # data slip through to a public surface, so this must raise, not pass
    # the value through untouched.
    with pytest.raises(TypeError):
        sanitize_value({"weird": {1, 2, 3}})
