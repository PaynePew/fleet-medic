"""prune_images: reclaims disk from superseded docker images (runbook Branch
B). Two-phase (dry-run computes candidates + a confirm_token; apply removes
them) — with the hard invariant that an image backing a running container
never enters the candidate list, re-verified fresh at apply time, not
trusted from the dry-run (CONTEXT.md 白名單對不變量)."""

from __future__ import annotations

import pytest

from ops_mcp.command_runner import CommandResult
from ops_mcp.tools.prune import (
    IMAGES_COMMAND,
    RUNNING_CONTAINERS_COMMAND,
    prune_images,
    running_image_ids_command,
)

IMAGES_OUTPUT = (
    "sha256:aaa::app/edge::latest::120MB\n"
    "sha256:bbb::app/edge::old::118MB\n"
    "sha256:ccc::app/rag::latest::300MB\n"
)


def _script_inventory(responses, *, running_ids=None, image_ids_by_container=None):
    running_ids = running_ids or []
    responses[tuple(RUNNING_CONTAINERS_COMMAND)] = CommandResult(
        stdout="\n".join(running_ids), stderr="", returncode=0
    )
    if running_ids:
        cmd = tuple(running_image_ids_command(running_ids))
        image_ids = image_ids_by_container or []
        responses[cmd] = CommandResult(stdout="\n".join(image_ids), stderr="", returncode=0)
    responses[tuple(IMAGES_COMMAND)] = CommandResult(stdout=IMAGES_OUTPUT, stderr="", returncode=0)


def test_dry_run_lists_candidates_and_never_changes_the_system(scripted_runner):
    runner, responses = scripted_runner
    # container "c1" is running app/edge:latest (sha256:aaa) — that image must
    # never appear as a candidate; nothing else is running.
    _script_inventory(responses, running_ids=["c1"], image_ids_by_container=["sha256:aaa"])

    result = prune_images(runner, dry_run=True)

    assert result["dry_run"] is True
    candidate_ids = {c["id"] for c in result["candidates"]}
    assert candidate_ids == {"sha256:bbb", "sha256:ccc"}
    assert "confirm_token" in result and result["confirm_token"]
    # No `docker image rm` (or anything beyond the read-only inventory calls)
    # was scripted — an unscripted command would already have raised inside
    # scripted_runner, so reaching here is itself proof dry-run stayed read-only.


def test_in_use_image_never_enters_the_candidate_list(scripted_runner):
    runner, responses = scripted_runner
    _script_inventory(
        responses, running_ids=["c1", "c2"], image_ids_by_container=["sha256:aaa", "sha256:ccc"]
    )

    result = prune_images(runner, dry_run=True)

    candidate_ids = {c["id"] for c in result["candidates"]}
    assert "sha256:aaa" not in candidate_ids
    assert "sha256:ccc" not in candidate_ids
    assert candidate_ids == {"sha256:bbb"}


def test_apply_without_confirm_token_is_refused(scripted_runner):
    runner, responses = scripted_runner
    _script_inventory(responses)

    with pytest.raises(ValueError, match="confirm_token"):
        prune_images(runner, dry_run=False)


def test_apply_with_a_valid_token_removes_the_candidates(scripted_runner):
    runner, responses = scripted_runner
    _script_inventory(responses, running_ids=["c1"], image_ids_by_container=["sha256:aaa"])
    dry_run_result = prune_images(runner, dry_run=True)
    token = dry_run_result["confirm_token"]

    _script_inventory(responses, running_ids=["c1"], image_ids_by_container=["sha256:aaa"])
    responses[("docker", "image", "rm", "sha256:bbb", "sha256:ccc")] = CommandResult(
        stdout="Deleted: sha256:bbb\nDeleted: sha256:ccc\n", stderr="", returncode=0
    )

    result = prune_images(runner, dry_run=False, confirm_token=token)

    assert result["dry_run"] is False
    assert set(result["removed_image_ids"]) == {"sha256:bbb", "sha256:ccc"}


def test_apply_rejects_a_stale_token_when_the_box_state_drifted(scripted_runner):
    runner, responses = scripted_runner
    # Dry-run sees only c1 running app/edge:latest -> candidates {bbb, ccc}.
    _script_inventory(responses, running_ids=["c1"], image_ids_by_container=["sha256:aaa"])
    token = prune_images(runner, dry_run=True)["confirm_token"]

    # Before apply, someone starts a second container on app/rag:latest
    # (sha256:ccc) — the real candidate set shrank to {bbb} since ccc is now
    # in use. Apply must detect this drift and refuse, not silently prune the
    # stale (now-wrong) list.
    _script_inventory(
        responses, running_ids=["c1", "c2"], image_ids_by_container=["sha256:aaa", "sha256:ccc"]
    )

    with pytest.raises(ValueError, match="drift"):
        prune_images(runner, dry_run=False, confirm_token=token)


def test_apply_with_no_candidates_is_a_no_op(scripted_runner):
    runner, responses = scripted_runner
    # Everything is in use.
    _script_inventory(
        responses,
        running_ids=["c1", "c2", "c3"],
        image_ids_by_container=["sha256:aaa", "sha256:bbb", "sha256:ccc"],
    )
    token = prune_images(runner, dry_run=True)["confirm_token"]

    _script_inventory(
        responses,
        running_ids=["c1", "c2", "c3"],
        image_ids_by_container=["sha256:aaa", "sha256:bbb", "sha256:ccc"],
    )

    result = prune_images(runner, dry_run=False, confirm_token=token)

    assert result["removed_image_ids"] == []


def test_dry_run_bounds_the_candidate_list(scripted_runner):
    runner, responses = scripted_runner
    many_images = "\n".join(f"sha256:img{i}::app/x::v{i}::10MB" for i in range(30))
    responses[tuple(RUNNING_CONTAINERS_COMMAND)] = CommandResult(stdout="", stderr="", returncode=0)
    responses[tuple(IMAGES_COMMAND)] = CommandResult(stdout=many_images, stderr="", returncode=0)

    result = prune_images(runner, dry_run=True, top_n=10)

    assert len(result["candidates"]) == 10
    assert result["candidates_total"] == 30
    assert result["candidates_truncated"] == 20


def test_dry_run_raises_clearly_when_docker_images_fails(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(RUNNING_CONTAINERS_COMMAND)] = CommandResult(stdout="", stderr="", returncode=0)
    responses[tuple(IMAGES_COMMAND)] = CommandResult(
        stdout="", stderr="Cannot connect to the Docker daemon", returncode=1
    )

    with pytest.raises(RuntimeError, match="docker images"):
        prune_images(runner, dry_run=True)
