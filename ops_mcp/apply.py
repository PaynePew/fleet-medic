"""Deterministic entry point for the gated box-mutations apply job (issue
#13; ADR-0004 Option A). The workflow job that runs this declares
`environment: box-mutations`, so a human reviewer has approved this specific
run before the process starts (ADR-0002's L2 gate), and it is the only place
`OPS_RW_SSH_KEY_PATH` is ever wired. No LLM is present in this process —
approval binds to one dry-run plan via its confirm_token, and the write tool
itself re-verifies fresh box state and rejects on drift/expiry before
touching anything (write_plan.py).

This is Option A's thin entry — it calls the write tools' own apply mode —
not Option C's independent executor (a Phase 2 upgrade that would consume a
plan artifact without the MCP tool layer; see ADR-0004 Recommendation).

Inputs arrive from the workflow_dispatch form as env vars (APPLY_ACTION /
APPLY_SERVICE / APPLY_CONFIRM_TOKEN). Output goes to stdout for the Actions
log — a public surface, so both the success payload and the failure
one-liner pass the shared sanitizer boundary first (ADR-0003; same
convention as sensor.main).
"""

from __future__ import annotations

import json
import os
import sys

from ops_mcp.command_runner import CommandRunner
from ops_mcp.sanitize import sanitize_text, sanitize_value
from ops_mcp.tools.prune import prune_images
from ops_mcp.tools.rotate import rotate_logs


def run_apply(
    runner: CommandRunner,
    *,
    action: str,
    confirm_token: str,
    service: str = "",
) -> dict:
    """Dispatch one approved plan to the matching write tool's apply mode.
    Raises ValueError on malformed inputs; drift/expiry rejection happens
    inside the tool, against fresh box state."""
    if not confirm_token:
        raise ValueError(
            "apply: confirm_token is required — approval binds to one dry-run plan"
        )
    if action == "prune_images":
        if service:
            raise ValueError("apply: service is only valid for rotate_logs")
        return prune_images(runner, dry_run=False, confirm_token=confirm_token)
    if action == "rotate_logs":
        if not service:
            raise ValueError("apply: rotate_logs requires a service")
        return rotate_logs(runner, service, dry_run=False, confirm_token=confirm_token)
    raise ValueError(f"apply: unknown action {action!r}")


def _apply_from_env() -> dict:
    # Imported lazily so listing/testing this module never requires the write
    # credential — only the gated job, which actually has it, reaches this.
    from ops_mcp.server import _rw_ssh_runner

    return run_apply(
        _rw_ssh_runner(),
        action=os.environ.get("APPLY_ACTION", ""),
        confirm_token=os.environ.get("APPLY_CONFIRM_TOKEN", ""),
        service=os.environ.get("APPLY_SERVICE", ""),
    )


def main() -> None:
    host = os.environ.get("OPS_BOX_HOST")
    try:
        result = _apply_from_env()
    except Exception as exc:
        # ADR-0003: an unhandled exception's default traceback would print a
        # command's raw stderr straight to the (public) Actions log — the
        # exact box-path/IP/host leak shape the sanitizer boundary closes.
        # Report a sanitized one-liner and fail the step instead.
        print(f"apply: failed: {sanitize_text(str(exc), host=host)}", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(sanitize_value(result, host=host), indent=2))


if __name__ == "__main__":
    main()
