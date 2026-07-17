"""sensor: fleet-medic's deterministic wakeup layer (CONTEXT.md — Sensor /
Tripwire / Anomaly Snapshot; ADR-0001 — LLM never enters this package).
Runs from `.github/workflows/sensor.yml` on a schedule; reuses the ops_mcp
read tools for the actual SSH/gh calls rather than reimplementing them.
"""

from __future__ import annotations
