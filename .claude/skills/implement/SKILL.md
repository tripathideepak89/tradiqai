---
name: "Implement"
description: "Execute an implementation plan step-by-step, tracking progress with todos, verifying each step works before moving on, and summarising what was done."
---

# Implement Skill

Your job is to execute a plan precisely and carefully — one step at a time, verifying as you go.

## Process

1. **Load the plan** — Ask the user for the plan (from `/plan`) if not already in context. Do not start coding without a plan.

2. **Create a todo list** — Break the plan into discrete tasks using TodoWrite. Mark each task as you complete it.

3. **Execute step by step**:
   - Complete one step fully before moving to the next
   - Read files before editing them
   - Make the minimal change needed — do not add unrequested features, refactors, or cleanup
   - After each step, verify it works (run tests if available, check for syntax errors, check imports)

4. **When a step fails or surprises you**:
   - Stop and diagnose before continuing
   - If the plan was wrong, explain what you found and propose an adjustment
   - Do NOT bulldoze past errors or try the same failing approach repeatedly

5. **After all steps are complete**, write a short summary:

```
## Implementation Complete: <feature name>

### What was done
- Bullet list of actual changes made (with file references)

### What was NOT done / deferred
- Anything skipped with reason

### How to verify
- Step-by-step manual test instructions
- Which automated tests to run

### Follow-up
- Any technical debt introduced
- Recommended next steps
```

## Rules
- **Read before editing** — always use the Read tool before making changes to a file.
- **Minimal changes** — only change what the plan requires. Leave surrounding code alone.
- **No speculative improvements** — do not refactor, rename, or "clean up" code not directly related to the task.
- **Stop on blockers** — if something is blocked (missing env var, failing import, API error), surface it immediately. Do not retry the same thing repeatedly.
- **Commit-ready output** — each step should produce code that compiles/runs. No half-done changes.
- **One file at a time** — complete edits to one file before moving to the next where possible.
