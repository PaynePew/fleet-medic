"""ops_mcp.server: the FastMCP app Claude Code (or any MCP client) mounts
directly — verifies all five read tools register with real descriptions
(描述即 prompt) and are actually callable through the MCP protocol layer,
not just as plain Python functions."""

from __future__ import annotations

import asyncio
import json

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from ops_mcp import server
from ops_mcp.command_runner import CommandResult

EXPECTED_TOOLS = {
    "get_vitals",
    "disk_breakdown",
    "tail_logs",
    "list_recent_deploys",
    "read_runbook",
}


def _call(tool_name: str, arguments: dict | None = None) -> dict:
    blocks = asyncio.run(server.mcp.call_tool(tool_name, arguments or {}))
    return json.loads(blocks[0].text)


def test_all_five_read_tools_are_registered_with_real_descriptions():
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS
    for tool in tools:
        assert tool.description and len(tool.description.strip()) > 20, tool.name


def test_read_runbook_callable_through_mcp_end_to_end():
    # No runner/credentials needed — read_runbook is a plain file read, and
    # doubles as a smoke test that the tool is wired correctly.
    result = _call("read_runbook", {"topic": "disk-full"})
    assert result["topic"] == "disk-full"
    assert "docker_system_df" not in result  # sanity: didn't call the wrong tool


def test_get_vitals_raises_clearly_without_ssh_env(monkeypatch):
    monkeypatch.delenv("OPS_BOX_HOST", raising=False)
    monkeypatch.delenv("OPS_RO_SSH_KEY_PATH", raising=False)
    server._ssh_runner.cache_clear()

    with pytest.raises(ToolError, match="OPS_BOX_HOST"):
        _call("get_vitals")


def test_get_vitals_uses_the_injected_runner(monkeypatch):
    df_output = (
        "Filesystem     1024-blocks     Used Available Capacity Mounted on\n"
        "/dev/sda1         20642428 17332708   2242496      89% /\n"
    )

    def fake_runner(command):
        if command[0] == "df":
            return CommandResult(stdout=df_output, stderr="", returncode=0)
        return CommandResult(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(server, "_ssh_runner", lambda: fake_runner)

    result = _call("get_vitals")

    assert result["disk_percent"] == 89.0


def test_tail_logs_uses_the_injected_runner(monkeypatch):
    def fake_runner(command):
        return CommandResult(stdout="l1\nl2\n", stderr="", returncode=0)

    monkeypatch.setattr(server, "_ssh_runner", lambda: fake_runner)

    result = _call("tail_logs", {"service": "edge", "lines": 2})

    assert result["service"] == "edge"
    assert result["lines"] == ["l1", "l2"]


def test_disk_breakdown_uses_the_injected_runner(monkeypatch):
    def fake_runner(command):
        if command[0] == "du":
            return CommandResult(stdout="1000\t/var/lib/docker\n", stderr="", returncode=0)
        return CommandResult(stdout="Images::1::1::1B::0B\n", stderr="", returncode=0)

    monkeypatch.setattr(server, "_ssh_runner", lambda: fake_runner)

    result = _call("disk_breakdown")

    assert result["top_paths"][0]["path"] == "/var/lib/docker"
    assert result["docker_system_df"][0]["type"] == "Images"


def test_list_recent_deploys_uses_the_local_runner(monkeypatch):
    def fake_runner(command):
        return CommandResult(stdout="[]", stderr="", returncode=0)

    monkeypatch.setattr(server, "_gh_runner", lambda: fake_runner)

    result = _call("list_recent_deploys")

    assert result == {"deploys": [], "count_returned": 0, "truncated": False}
