# ops/ — box-side operational artifacts (version-controlled)

Safety-critical box-side scripts live here under version control and test,
rather than only in the box's `authorized_keys` / `/usr/local/bin`
(arch-review 2026-07-18; ADR-0003).

## `ops-ro-guard`

The forced-command dispatcher pinned by the `ops-ro` key's `authorized_keys`
line (`command="/usr/local/bin/ops-ro-guard"`). It keeps the read-only key
read-only: rejects an empty command (no interactive shell), rejects shell
metacharacters, and passes only a read-only docker/df/du allowlist
(ADR-0002 credential split; ADR-0003 for the SSH-channel constraints the
read tools must satisfy).

**This file is the source of truth.** The box copy must be deployed from here.
Tested by `tests/test_ops_ro_guard.py` (validate-only via `OPS_RO_GUARD_CHECK=1`,
so tests never execute the underlying command).

To deploy to a box:

```sh
scp ops/ops-ro-guard <admin>@<box>:/tmp/ops-ro-guard
ssh <admin>@<box> "sudo install -o root -g root -m 755 /tmp/ops-ro-guard /usr/local/bin/ops-ro-guard && rm /tmp/ops-ro-guard"
```

## `ops-rw-guard`

The forced-command dispatcher pinned by the `ops-rw` key's `authorized_keys`
line (`command="/usr/local/bin/ops-rw-guard"`) — issue #13, ADR-0004 Option A.
Intentionally narrower than `ops-ro-guard`: it allowlists only the exact
apply-mode argv the write tools send — their fresh-state re-verification
reads plus the two write shapes (`docker image rm sha256:…`,
`truncate -s 0 /var/lib/docker/containers/…`). General diagnosis reads ride
the ops-ro key, never this one.

**This file is the source of truth.** The box copy must be deployed from here.
Tested by `tests/test_ops_rw_guard.py` (validate-only via `OPS_RW_GUARD_CHECK=1`).

To deploy to a box:

```sh
scp ops/ops-rw-guard <admin>@<box>:/tmp/ops-rw-guard
ssh <admin>@<box> "sudo install -o root -g root -m 755 /tmp/ops-rw-guard /usr/local/bin/ops-rw-guard && rm /tmp/ops-rw-guard"
```
