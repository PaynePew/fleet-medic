"""Injectable shell/SSH execution seam shared by every ops_mcp read tool.

Read tools depend on the `CommandRunner` type, never on `subprocess` directly
— that is what lets tests substitute canned df/du/docker/gh output instead of
touching a real shell or network (CODING_STANDARDS §4). Production wiring
picks `ssh_command_runner` for VPS-bound commands (ADR-0002: the agent lives
off-box, so diagnosis is always a remote call) or `local_command_runner` for
commands that run where the Agent itself runs (e.g. `gh`, against GitHub).
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass

_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class CommandResult:
    """One command's outcome — the shape every CommandRunner returns."""

    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


CommandRunner = Callable[[list[str]], CommandResult]
"""argv in, CommandResult out. Tools take this as a parameter instead of
importing subprocess/ssh themselves, so a fake can stand in during tests."""


def local_command_runner() -> CommandRunner:
    """Build a CommandRunner that runs `command` as a local subprocess."""

    def run(command: list[str]) -> CommandResult:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS)
        return CommandResult(stdout=proc.stdout, stderr=proc.stderr, returncode=proc.returncode)

    return run


def ssh_command_runner(*, host: str, user: str, identity_file: str) -> CommandRunner:
    """Build a CommandRunner that runs `command` on `host` over the read-only
    `ops-ro` key (authorized_keys `command=`-locked; ADR-0002)."""

    def run(command: list[str]) -> CommandResult:
        ssh_argv = [
            "ssh",
            "-i", identity_file,
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            f"{user}@{host}",
            "--",
            *command,
        ]
        proc = subprocess.run(ssh_argv, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS)
        return CommandResult(stdout=proc.stdout, stderr=proc.stderr, returncode=proc.returncode)

    return run


def run_checked(runner: CommandRunner, command: list[str], error_prefix: str) -> CommandResult:
    """Run `command` and raise RuntimeError(f"{error_prefix}: {stderr}") on failure.

    Every read tool needs this exact check-and-raise shape after each command
    it runs, so it lives here once instead of being repeated in each tool.
    """
    result = runner(command)
    if not result.ok:
        raise RuntimeError(f"{error_prefix}: {result.stderr.strip()}")
    return result
