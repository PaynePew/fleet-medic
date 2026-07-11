# TASK

Review and refine the changes on branch {{BRANCH}} for issue {{ISSUE_ID}}.
Role: a reviewer focused on clarity, consistency, and maintainability — while PRESERVING exact behavior.

# CONTEXT

- Issue: title is `{{ISSUE_ID}}`; if it is a GitHub issue number, `gh issue view {{ISSUE_ID}}` for full context
- Your diff: `git diff main..{{BRANCH}}` (you are already on {{BRANCH}})
- Standards: read {{STANDARDS}} and apply them. CLAUDE.md 硬約束違反=FAIL,不是 style nit。

# IMPROVE

- reduce complexity / nesting; remove redundancy; clarify names; consolidate related logic
- remove comments that just restate obvious code
- prefer if/else or switch over nested ternaries
- clarity over cleverness

# DO NOT OVER-SIMPLIFY

- don't harm readability, don't merge unrelated concerns, don't remove helpful abstractions, don't make it harder to debug or extend

# PRESERVE BEHAVIOR

Never change WHAT the code does — only HOW. All outputs and behaviors must stay identical.

# EXECUTION

If improvements exist: make them directly on {{BRANCH}}, run `uv run ruff check .` + `uv run pytest`, commit following Conventional Commits (`refactor: ... (review pass)`).
If the code is already clean, do nothing.

# RETURN

One line: what you refined (or "clean").
