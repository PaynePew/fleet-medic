# TASK

Merge these branches into the current (default) branch, one at a time:

{{BRANCHES}}

For each branch:
1. `git merge <branch> --no-edit`
2. If conflicts: read both sides and resolve correctly
3. Run `uv run ruff check .` + `uv run pytest`; fix failures before moving to the next branch

# INTEGRATION GATE

After ALL branches are merged, run the FULL test suite once more on the integrated result and fix any breakage.
This catches semantic conflicts that merged cleanly but are wrong (e.g. A renamed a symbol, B added a caller of the old name).

Then make a single commit summarizing the merge (Conventional Commits, no AI attribution trailer).

# CLOSE ISSUES

Only if the ids in {{ISSUE_IDS}} are GitHub issue numbers (this repo uses GitHub issues):
`gh issue close <id> --comment "merged into <default-branch> at <merge-commit-sha>"`
If the ids are not GitHub issues (explicit slices passed to the orchestrator), skip closing — there is nothing to close.

# RETURN

A summary: branches merged, ids closed (or "no tracker"), and any branch you could NOT merge (with the reason).
