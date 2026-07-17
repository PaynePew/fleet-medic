"""read_runbook: read a human-authored runbook so the Agent's decision order
is grounded in operator experience instead of reinvented per incident
(roadmap.md Phase 1: markdown-only, `read_runbook(topic)` = 讀檔; kb_mcp-style
retrieval is deferred to Phase 3+)."""

from __future__ import annotations

import re
from pathlib import Path

_TOPIC_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
MAX_RUNBOOK_CHARS = 20_000
DEFAULT_RUNBOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "runbooks"


def read_runbook(
    topic: str,
    runbooks_dir: Path = DEFAULT_RUNBOOKS_DIR,
    max_chars: int = MAX_RUNBOOK_CHARS,
) -> dict:
    """Return the runbook markdown for `topic` (runbooks/<topic>.md).

    `topic` is boundary input from the LLM, so it is restricted to a bare
    identifier before touching the filesystem — no path separators or `..`
    can escape `runbooks_dir`.
    """
    if not topic or not _TOPIC_RE.match(topic):
        raise ValueError(f"read_runbook: topic must match {_TOPIC_RE.pattern!r}, got {topic!r}")

    path = Path(runbooks_dir) / f"{topic}.md"
    if not path.is_file():
        raise FileNotFoundError(f"read_runbook: no runbook for topic={topic!r} (looked for {path})")

    text = path.read_text(encoding="utf-8")
    truncated = len(text) > max_chars
    return {
        "topic": topic,
        "content": text[:max_chars],
        "truncated": truncated,
    }
