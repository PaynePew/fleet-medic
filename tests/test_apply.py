"""ops_mcp.apply: the deterministic entry the gated box-mutations job runs
(issue #13; ADR-0004 Option A). `run_apply` dispatches one approved plan to
the matching write tool's apply mode; `main`'s sanitize-before-log error
boundary keeps a failed apply from leaking raw box output into the (public)
Actions log — same convention as sensor.main."""

from __future__ import annotations

import pytest

from ops_mcp.apply import main, run_apply
from ops_mcp.command_runner import CommandResult
from ops_mcp.tools.prune import IMAGES_COMMAND, RUNNING_CONTAINERS_COMMAND, prune_images
from ops_mcp.tools.rotate import log_path_command, log_size_command, rotate_logs, truncate_command

_LOG_PATH = "/var/lib/docker/containers/abc/abc-json.log"


def _script_prune(responses):
    responses[tuple(RUNNING_CONTAINERS_COMMAND)] = CommandResult(
        stdout="", stderr="", returncode=0
    )
    responses[tuple(IMAGES_COMMAND)] = CommandResult(
        stdout="sha256:aaa::old::v1::100MB\n", stderr="", returncode=0
    )


def _script_rotate(responses, *, service="edge"):
    responses[tuple(log_path_command(service))] = CommandResult(
        stdout=f"{_LOG_PATH}\n", stderr="", returncode=0
    )
    responses[tuple(log_size_command(_LOG_PATH))] = CommandResult(
        stdout=f"12345\t{_LOG_PATH}\n", stderr="", returncode=0
    )


def test_apply_prune_images_with_valid_token(scripted_runner):
    runner, responses = scripted_runner
    _script_prune(responses)
    token = prune_images(runner, dry_run=True)["confirm_token"]

    _script_prune(responses)  # apply re-verifies fresh state
    responses[("docker", "image", "rm", "sha256:aaa")] = CommandResult(
        stdout="", stderr="", returncode=0
    )

    result = run_apply(runner, action="prune_images", confirm_token=token)

    assert result["dry_run"] is False
    assert result["removed_image_ids"] == ["sha256:aaa"]


def test_apply_rotate_logs_with_valid_token(scripted_runner):
    runner, responses = scripted_runner
    _script_rotate(responses)
    token = rotate_logs(runner, "edge", dry_run=True)["confirm_token"]

    _script_rotate(responses)
    responses[tuple(truncate_command(_LOG_PATH))] = CommandResult(
        stdout="", stderr="", returncode=0
    )

    result = run_apply(runner, action="rotate_logs", service="edge", confirm_token=token)

    assert result["rotated"] is True


def test_apply_refuses_bad_inputs(scripted_runner):
    runner, _ = scripted_runner
    cases = [
        # (action, service, confirm_token, match)
        ("reboot_box", "", "tok", "unknown action"),
        ("rotate_logs", "", "tok", "service"),
        ("prune_images", "edge", "tok", "service"),
        ("prune_images", "", "", "confirm_token"),
    ]
    for action, service, token, match in cases:
        with pytest.raises(ValueError, match=match):
            run_apply(runner, action=action, service=service, confirm_token=token)


def test_main_error_boundary_sanitizes_before_the_public_log(monkeypatch, capsys):
    # A failed apply's message can carry a command's raw stderr — the exact
    # IP/path/host leak shape ADR-0003 closes. main must print a sanitized
    # one-liner and exit 1, never a raw traceback.
    monkeypatch.setattr(
        "ops_mcp.apply._apply_from_env",
        lambda: (_ for _ in ()).throw(
            RuntimeError("ssh: connect to host 203.0.113.7 failed for /home/deploy/x")
        ),
    )

    with pytest.raises(SystemExit) as excinfo:
        main()

    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "203.0.113.7" not in err
    assert "/home/deploy" not in err
    assert "[REDACTED-IP]" in err


def test_main_sanitizes_the_success_payload_too(monkeypatch, capsys):
    monkeypatch.setattr(
        "ops_mcp.apply._apply_from_env",
        lambda: {"rotated": True, "log_path": "/home/deploy/leaky.log"},
    )

    main()

    out = capsys.readouterr().out
    assert "/home/deploy" not in out
    assert "[REDACTED-USER]" in out
