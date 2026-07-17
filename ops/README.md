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
