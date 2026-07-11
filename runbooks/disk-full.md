# Runbook: disk-full

> Read by `read_runbook("disk-full")`. Audience: the Agent Loop, mid-Incident,
> right after a Tripwire (df>80%) hands it an Anomaly Snapshot. This is the
> operator's prescribed diagnosis order — follow it before improvising.

## Triage order

1. `get_vitals()` — confirm the disk_percent is still high and check whether
   any service is already unhealthy or restart-looping (a symptom, not the
   cause, but worth noting for the report).
2. `disk_breakdown()` — this is the fork point. Compare `top_paths` against
   `docker_system_df` to pick one of the three branches below. Don't guess;
   the numbers tell you which branch you're in.
3. Once a branch is picked, follow its own steps, then always close with
   `get_vitals()` again as Verification — 工具執行成功不是驗證,df% actually
   dropping is.

## Branch A — 大檔在上傳暫存(large file in an upload staging dir)

Signature: one `top_paths` entry (typically under a tenant's upload/tmp
directory) accounts for most of the usage; `docker_system_df` looks ordinary.

- Confirm with `tail_logs(<tenant service>)` — an upload or ingest job
  usually logs the file it was writing right before disk filled up.
- This branch has no safe automated remediation in Phase 1 (deleting a
  tenant's in-progress upload is not a whitelistable action) — file the
  Incident Report with the offending path and stop at L1 (propose only).

## Branch B — superseded images(昨夜部署留下的舊 image layers)

Signature: `docker_system_df` shows a large `Images` row with a high
reclaimable fraction; `top_paths` points at the docker root
(e.g. `/var/lib/docker`).

- Cross-check with `list_recent_deploys()` — if the last 1-3 deploys line up
  with when disk started filling, that corroborates this branch.
- Remediation: `prune_images(dry_run=true)` first — inspect the projected
  reclaim and the image list (dry-run 先行 + confirm token 兩段式; the tool
  itself refuses to touch any image backing a running container). Propose to
  the human at L1/L2 with the dry-run evidence attached; only call
  `prune_images` with the confirm token after approval.

## Branch C — log 膨脹(a service's logs grew unbounded)

Signature: `top_paths` points at a log directory or a specific container's
log file; `docker_system_df` looks ordinary.

- Confirm with `tail_logs(<service>)` — repetitive or runaway output (crash
  loop stack traces, verbose debug logging left on) is the usual cause.
- Remediation: `rotate_logs(dry_run=true)` first, same two-段 dry-run +
  confirm pattern as Branch B. If the underlying cause is a crash loop, note
  in the Incident Report that log rotation only buys space back — the loop
  itself is a separate finding.

## After any remediation

Re-run `get_vitals()`. If disk_percent is still above the tripwire threshold,
do not declare victory — re-enter triage from step 2; a second branch may be
contributing at the same time.
