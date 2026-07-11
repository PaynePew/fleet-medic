# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the project glossary (Sensor / Tripwire / 異常快照 / Autonomy Ladder / 白名單對 / Run Ledger / Chaos Eval).
- **`project-docs/adr/`** — read ADRs that touch the area you're about to work in. This repo keeps ADRs here, **not** at the default `docs/adr/`.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

Single-context repo:

```
/
├── CLAUDE.md
├── CONTEXT.md
└── project-docs/
    ├── roadmap.md
    ├── architecture/
    │   └── system-overview.md
    └── adr/
        ├── 0001-llm-never-in-the-polling-loop.md
        └── 0002-agent-lives-off-box.md
```

New ADRs go in `project-docs/adr/`, numbered sequentially.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids — CLAUDE.md enforces this ("用這些詞,不要發明同義詞").

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0001 (LLM never in the polling loop) — but worth reopening because…_
