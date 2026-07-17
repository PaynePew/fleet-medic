"""read_runbook: read a human-authored runbook so the Agent's decision order
is grounded in operator experience instead of reinvented per incident
(roadmap.md Phase 1: markdown-only, read_runbook(topic) = 讀檔)."""

from __future__ import annotations

import pytest

from ops_mcp.tools.runbook import read_runbook


def test_read_runbook_happy_returns_file_content(tmp_path):
    runbooks_dir = tmp_path / "runbooks"
    runbooks_dir.mkdir()
    (runbooks_dir / "disk-full.md").write_text("# Disk Full\n\nstep 1\n", encoding="utf-8")

    result = read_runbook("disk-full", runbooks_dir=runbooks_dir)

    assert result["topic"] == "disk-full"
    assert result["content"] == "# Disk Full\n\nstep 1\n"
    assert result["truncated"] is False


def test_read_runbook_raises_when_missing(tmp_path):
    runbooks_dir = tmp_path / "runbooks"
    runbooks_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="oom"):
        read_runbook("oom", runbooks_dir=runbooks_dir)


def test_read_runbook_rejects_empty_topic(tmp_path):
    with pytest.raises(ValueError):
        read_runbook("", runbooks_dir=tmp_path)


def test_read_runbook_rejects_path_traversal(tmp_path):
    # A topic that would escape runbooks_dir must never touch the filesystem.
    outside = tmp_path.parent / "secret.md"
    outside.write_text("nope", encoding="utf-8")

    with pytest.raises(ValueError):
        read_runbook("../secret", runbooks_dir=tmp_path / "runbooks")


def test_read_runbook_bounds_content_length(tmp_path):
    runbooks_dir = tmp_path / "runbooks"
    runbooks_dir.mkdir()
    (runbooks_dir / "chatty.md").write_text("x" * 100, encoding="utf-8")

    result = read_runbook("chatty", runbooks_dir=runbooks_dir, max_chars=10)

    assert len(result["content"]) == 10
    assert result["truncated"] is True


def test_read_runbook_default_dir_reads_real_disk_full_runbook():
    result = read_runbook("disk-full")

    assert "disk" in result["content"].lower() or "磁碟" in result["content"]
    assert result["truncated"] is False
