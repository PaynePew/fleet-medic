"""prune_images: reclaims disk from superseded docker images (runbook
disk-full Branch B). Two-phase like every ops_mcp write tool (ADR-0004):
dry_run=True computes which images no running container depends on and
returns a confirm_token bound to that exact candidate list; dry_run=False
requires that token, recomputes the candidate list from fresh box state
first (rejecting on drift — CONTEXT.md 白名單對不變量: the in-use check is a
tool-side deterministic re-verification, never trusted from an earlier
call), and only then removes them.

Known simplification: candidates are filtered against *running* containers
only (matching runbooks/disk-full.md's own wording and CONTEXT.md's
白名單對 example), not stopped-but-not-removed ones. `docker image rm`
itself still independently refuses an image referenced by a stopped
container, so the worst case is apply reporting a docker-side removal
failure for that id, not a silent deletion.
"""

from __future__ import annotations

from ops_mcp.bounds import DEFAULT_TOP_N, take_top_n
from ops_mcp.command_runner import CommandRunner, run_checked
from ops_mcp.write_plan import issue_confirm_token, verify_confirm_token

RUNNING_CONTAINERS_COMMAND = ["docker", "ps", "-q"]
# `::` field separator, not a TAB — a TAB would word-split when the ops-rw
# guard's `sh -c` re-parses the flattened SSH argv (ADR-0003, same rule as
# disk.py/vitals.py's own `--format` strings).
IMAGES_COMMAND = [
    "docker", "images", "--no-trunc", "--format", "{{.ID}}::{{.Repository}}::{{.Tag}}::{{.Size}}",
]


def running_image_ids_command(container_ids: list[str]) -> list[str]:
    """`docker inspect` argv for the images backing the given running
    container ids (no shell, no `$()` — same two-step pattern as
    vitals.py's `inspect_command`)."""
    return ["docker", "inspect", "--format", "{{.Image}}", *container_ids]


def _normalize_image_id(image_id: str) -> str:
    # `docker images --no-trunc` and `docker inspect --format {{.Image}}`
    # aren't guaranteed to agree on the `sha256:` prefix across versions;
    # compare on the hash itself so a formatting quirk can't defeat the
    # in-use match.
    return image_id.removeprefix("sha256:")


def _parse_images(images_output: str) -> list[dict]:
    images = []
    for line in images_output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("::")
        if len(parts) != 4:
            raise ValueError(f"unexpected `docker images` line: {line!r}")
        image_id, repository, tag, size = parts
        images.append({"id": image_id, "repository": repository, "tag": tag, "size": size})
    # `docker images` only gives a docker-formatted size string (e.g.
    # "118MB"), not raw bytes, so there's no numeric "biggest first" to sort
    # by here — name order just keeps output (and the top_n cutoff below)
    # deterministic across calls.
    images.sort(key=lambda img: (img["repository"], img["tag"], img["id"]))
    return images


def _running_image_ids(runner: CommandRunner) -> set[str]:
    ps_result = run_checked(
        runner, RUNNING_CONTAINERS_COMMAND, "prune_images: `docker ps -q` failed"
    )
    container_ids = ps_result.stdout.split()
    if not container_ids:
        return set()
    inspect_result = run_checked(
        runner,
        running_image_ids_command(container_ids),
        "prune_images: `docker inspect` failed",
    )
    return {
        _normalize_image_id(line.strip())
        for line in inspect_result.stdout.splitlines()
        if line.strip()
    }


def _compute_candidates(runner: CommandRunner, top_n: int) -> tuple[list[dict], int]:
    running_ids = _running_image_ids(runner)

    images_result = run_checked(runner, IMAGES_COMMAND, "prune_images: `docker images` failed")
    all_images = _parse_images(images_result.stdout)

    candidates = [
        img for img in all_images if _normalize_image_id(img["id"]) not in running_ids
    ]
    return take_top_n(candidates, top_n)


def _plan_key(candidates: list[dict]) -> dict:
    # Digest only *which images* would be removed — never their (docker-
    # formatted, non-numeric) size string, which isn't a safety-relevant
    # field and would add nothing but spurious drift risk.
    return {"action": "prune_images", "candidate_ids": sorted(c["id"] for c in candidates)}


def prune_images(
    runner: CommandRunner,
    *,
    dry_run: bool,
    confirm_token: str | None = None,
    top_n: int = DEFAULT_TOP_N,
    now: float | None = None,
) -> dict:
    """Two-phase prune. `dry_run=True` (default caller mode) only reads box
    state — see module docstring for the phase contract."""
    candidates, dropped = _compute_candidates(runner, top_n)
    plan_key = _plan_key(candidates)

    if dry_run:
        token = issue_confirm_token(plan_key, now=now)
        return {
            "dry_run": True,
            "candidates": candidates,
            "candidates_total": len(candidates) + dropped,
            "candidates_truncated": dropped,
            "confirm_token": token,
        }

    verify_confirm_token(confirm_token, plan_key, now=now)

    ids = [c["id"] for c in candidates]
    if ids:
        run_checked(
            runner, ["docker", "image", "rm", *ids], "prune_images: `docker image rm` failed"
        )

    return {"dry_run": False, "removed_image_ids": ids, "removed_count": len(ids)}
