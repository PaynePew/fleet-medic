# TASK

Implement issue {{ISSUE_ID}}: {{ISSUE_TITLE}}
Work on a SINGLE issue only, on branch {{BRANCH}}.

# CONTEXT

- Issue details: the title is `{{ISSUE_TITLE}}`. If `{{ISSUE_ID}}` is a GitHub issue number, run `gh issue view {{ISSUE_ID}}` for the full body and comments (and any parent issue it references).
- Recent history: run `git log -n 10 --format="%H %ad %s" --date=short`.
- Coding standards: read {{STANDARDS}} and follow it (write to-standard the first time — saves a review round).
- fleet-medic specifics: CLAUDE.md 的「硬約束」節違反=審查 FAIL;用 CONTEXT.md 的語彙(Sensor/Tripwire/異常快照/…),不要發明同義詞;相關 ADR 在 project-docs/adr/。

# EXPLORATION

Explore the repo and load the code + tests relevant to this issue. Pay extra attention to tests touching the affected code.

# EXECUTION — Red / Green / Refactor

1. RED: write one failing test
2. GREEN: implement until it passes
3. REPEAT until the issue is done
4. REFACTOR

# FEEDBACK LOOP

Before every commit, run `uv run ruff check .` and `uv run pytest` and make them pass.
You may be running in parallel with other agents — use a RANDOM port, an isolated temp dir, and a per-worktree test DB so you don't collide with them.

# COMMIT

Commit on {{BRANCH}}. The message must:
1. follow Conventional Commits(feat/fix/refactor/docs/test/chore/perf/ci)— repo 慣例,無 AI attribution trailer
2. state the issue + what was done
3. note key decisions and follow-ups in the body

# IF INCOMPLETE

Record remaining work in your RETURN summary (and, if `{{ISSUE_ID}}` is a GitHub issue, `gh issue comment {{ISSUE_ID}} --body "<done so far / blockers>"`).
Do NOT close the issue — merge closes it later.

# DISCOVERED WORK

If you spot work outside this issue's scope, file it instead of doing it:
`gh issue create --title "<title>" --body "discovered while working on #{{ISSUE_ID}}"`. Don't do the work now.

# RETURN

A short summary: files changed, key decisions, and whether ruff/pytest are green.
