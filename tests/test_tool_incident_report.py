"""file_incident_report: closes an Incident as one gh issue with the fixed
five sections (CONTEXT.md Incident Report: 偵測→假設→行動→驗證→殘留風險).
Every section is required (tool-layer refusal on a missing one) and every
section is sanitized before the issue is created (ADR-0003 public-face
boundary)."""

from __future__ import annotations

import pytest

from ops_mcp.command_runner import CommandResult
from ops_mcp.tools.incident_report import INCIDENT_LABEL, file_incident_report

FULL_REPORT = dict(
    detection="disk_percent hit 92% on tick at 03:00 UTC",
    hypothesis="superseded image layers from last night's deploy (Branch B)",
    action="prune_images(dry_run=true) then apply after approval; see confirm_token digest abc123",
    verification="get_vitals() re-run: disk_percent now 61%",
    residual_risk="none observed; will re-check next tick",
)


def test_happy_path_creates_an_issue_with_all_five_sections():
    def runner_fn(command):
        assert command[0:3] == ["gh", "issue", "create"]
        body = command[command.index("--body") + 1]
        for heading in ("偵測", "假設", "行動", "驗證", "殘留風險"):
            assert heading in body
        assert "--label" in command
        assert command[command.index("--label") + 1] == INCIDENT_LABEL
        return CommandResult(
            stdout="https://github.com/example/repo/issues/99\n", stderr="", returncode=0
        )

    result = file_incident_report(runner_fn, **FULL_REPORT)

    assert result["url"] == "https://github.com/example/repo/issues/99"
    assert result["label"] == INCIDENT_LABEL


@pytest.mark.parametrize("missing_field", list(FULL_REPORT.keys()))
def test_missing_or_empty_section_is_refused(missing_field):
    unreachable = lambda cmd: (_ for _ in ()).throw(AssertionError("should not run"))  # noqa: E731
    fields = dict(FULL_REPORT)
    fields[missing_field] = "   "  # blank/whitespace-only counts as missing

    with pytest.raises(ValueError, match=missing_field):
        file_incident_report(unreachable, **fields)


def test_sanitizes_known_leak_shapes_before_creating_the_issue():
    captured = {}

    def runner_fn(command):
        captured["body"] = command[command.index("--body") + 1]
        return CommandResult(stdout="https://example/issues/1\n", stderr="", returncode=0)

    fields = dict(FULL_REPORT)
    fields["action"] = "ssh'd via 203.0.113.7 into /home/opsuser/box, ran prune"
    file_incident_report(runner_fn, host="fleet-box.example.com", **fields)

    body = captured["body"]
    assert "203.0.113.7" not in body
    assert "/home/opsuser" not in body
    assert "[REDACTED-IP]" in body
    assert "[REDACTED-USER]" in body


def test_raises_clearly_when_gh_issue_create_fails():
    def runner_fn(command):
        return CommandResult(stdout="", stderr="gh: authentication required", returncode=1)

    with pytest.raises(RuntimeError, match="gh issue create"):
        file_incident_report(runner_fn, **FULL_REPORT)
