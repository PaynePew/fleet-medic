"""sanitize: the shared public-output boundary (ADR-0003). fleet-medic runs
in a public repo, so every tool output that leaves the box and enters a
public surface (Actions run log, workflow artifact, Run Ledger) must pass
through this before it's printed, uploaded, or embedded anywhere the public
web can read it. This is deterministic code, not a prompt instruction
(CLAUDE.md / CODING_STANDARDS §1: 安全不外包給模型) — GitHub secret masking
(ADR-0003 option b) is a second line of defense, not a substitute for it.
"""

from __future__ import annotations

import re

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HOME_USER_RE = re.compile(r"/home/([^/\s]+)")
_REDACTED_IP = "[REDACTED-IP]"
_REDACTED_HOST = "[REDACTED-HOST]"
_REDACTED_USER = "[REDACTED-USER]"


def sanitize_text(text: str, *, host: str | None = None) -> str:
    """Mask the leak shapes ADR-0003 names — IP addresses, `/home/<user>`
    paths, and (when given) the exact box host string — in one pass of
    free-form text (e.g. a log line)."""
    sanitized = _IP_RE.sub(_REDACTED_IP, text)
    sanitized = _HOME_USER_RE.sub(f"/home/{_REDACTED_USER}", sanitized)
    if host:
        sanitized = sanitized.replace(host, _REDACTED_HOST)
    return sanitized


def sanitize_value(value, *, host: str | None = None):
    """Recursively apply `sanitize_text` through a tool-output structure
    (dict/list/str, as returned by any ops_mcp read tool); non-string JSON
    scalars pass through unchanged.

    Raises TypeError on any other type instead of passing it through
    unsanitized — a public-face boundary layer that silently fails open on
    an unrecognized type is the one bug this module is not allowed to have.
    """
    if isinstance(value, str):
        return sanitize_text(value, host=host)
    if isinstance(value, dict):
        return {key: sanitize_value(v, host=host) for key, v in value.items()}
    if isinstance(value, list):
        return [sanitize_value(v, host=host) for v in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    raise TypeError(f"sanitize_value: no rule for type {type(value).__name__}: {value!r}")
