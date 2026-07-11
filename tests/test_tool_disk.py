"""disk_breakdown: attributes disk usage to a cause (big files / superseded
images / log bloat) via top-N `du` paths + `docker system df` totals."""

from __future__ import annotations

import pytest

from ops_mcp.command_runner import CommandResult
from ops_mcp.tools.disk import DOCKER_DF_COMMAND, DU_COMMAND, disk_breakdown

DOCKER_DF_OUTPUT = (
    "Images\t12\t4\t6.2GB\t4.8GB (77%)\n"
    "Containers\t4\t4\t120MB\t0B (0%)\n"
    "Local Volumes\t3\t1\t540MB\t400MB (74%)\n"
    "Build Cache\t0\t0\t0B\t0B\n"
)


def _du_line(path: str, size_bytes: int) -> str:
    return f"{size_bytes}\t{path}"


def test_disk_breakdown_happy_sorts_paths_by_size_desc(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DU_COMMAND)] = CommandResult(
        stdout="\n".join([
            _du_line("/var/lib/docker", 1000),
            _du_line("/home/uploads", 5000),
            _du_line("/var/log", 200),
        ]),
        stderr="",
        returncode=0,
    )
    responses[tuple(DOCKER_DF_COMMAND)] = CommandResult(
        stdout=DOCKER_DF_OUTPUT, stderr="", returncode=0
    )

    result = disk_breakdown(runner)

    paths = [p["path"] for p in result["top_paths"]]
    assert paths == ["/home/uploads", "/var/lib/docker", "/var/log"]
    assert result["top_paths"][0]["size_bytes"] == 5000
    assert result["top_paths"][0]["human"] == "4.9K"


def test_disk_breakdown_parses_docker_system_df(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DU_COMMAND)] = CommandResult(
        stdout=_du_line("/var/lib/docker", 1000), stderr="", returncode=0
    )
    responses[tuple(DOCKER_DF_COMMAND)] = CommandResult(
        stdout=DOCKER_DF_OUTPUT, stderr="", returncode=0
    )

    result = disk_breakdown(runner)

    images_row = next(r for r in result["docker_system_df"] if r["type"] == "Images")
    assert images_row == {
        "type": "Images", "total": 12, "active": 4, "size": "6.2GB", "reclaimable": "4.8GB (77%)",
    }


def test_disk_breakdown_bounds_top_paths(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DU_COMMAND)] = CommandResult(
        stdout="\n".join(_du_line(f"/data/{i}", i) for i in range(30)),
        stderr="",
        returncode=0,
    )
    responses[tuple(DOCKER_DF_COMMAND)] = CommandResult(
        stdout=DOCKER_DF_OUTPUT, stderr="", returncode=0
    )

    result = disk_breakdown(runner, top_n=20)

    assert len(result["top_paths"]) == 20
    assert result["top_paths_total"] == 30
    assert result["top_paths_truncated"] == 10
    # biggest (i=29) sorts first
    assert result["top_paths"][0]["path"] == "/data/29"


def test_disk_breakdown_raises_clearly_when_du_fails(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DU_COMMAND)] = CommandResult(stdout="", stderr="du: permission denied", returncode=1)

    with pytest.raises(RuntimeError, match="du"):
        disk_breakdown(runner)


def test_disk_breakdown_raises_clearly_when_docker_df_fails(scripted_runner):
    runner, responses = scripted_runner
    responses[tuple(DU_COMMAND)] = CommandResult(
        stdout=_du_line("/var/lib/docker", 1000), stderr="", returncode=0
    )
    responses[tuple(DOCKER_DF_COMMAND)] = CommandResult(
        stdout="", stderr="Cannot connect to the Docker daemon", returncode=1
    )

    with pytest.raises(RuntimeError, match="docker system df"):
        disk_breakdown(runner)
