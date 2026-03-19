---
name: "Plan"
description: "Design a step-by-step implementation plan from a spec and research summary. Covers architecture decisions, file changes, order of work, and test strategy — before writing any code."
---

# Plan Skill

Your job is to design the implementation — not to write it. A good plan means the actual coding is mechanical execution with no surprises.

## Process

1. **Gather inputs** — You need at minimum a spec (from `/spec`). Research notes (from `/research`) are strongly recommended. Ask the user to provide them if missing.

2. **Design the solution** — Think through the architecture before writing the plan. Consider:
   - What is the simplest design that satisfies all requirements?
   - What existing code can be reused vs. what needs to change?
   - What is the right order of changes to keep the system working at every step?

3. **Write the plan** using this structure:

```
## Implementation Plan: <feature name>

### Approach
1-3 sentences describing the overall design strategy and key decisions made.

### Architecture Decisions
- Decision: <what was decided>
  Reason: <why this approach over alternatives>
- (one entry per significant decision)

### Files to Change
| File | Change Type | Description |
|------|-------------|-------------|
| path/to/file.py | Modify | Add X function, change Y behaviour |
| path/to/new.py  | Create  | New module for Z |
| path/to/old.py  | Delete  | Replaced by new.py |

### Implementation Steps
1. **Step name** — What to do and why this comes first
   - Sub-task a
   - Sub-task b
2. **Step name** — ...
   (Each step should leave the system in a working state)

### Test Strategy
- Unit tests: what to test and where
- Integration tests: what flows to verify end-to-end
- Manual verification steps

### Risks & Mitigations
- Risk: <what could go wrong>
  Mitigation: <how to handle it>
```

4. **Confirm before proceeding** — Present the plan and ask: "Does this look right? Say `/implement` to start coding, or tell me what to adjust."

## Rules
- Do NOT write any implementation code in the plan.
- Each step must leave the codebase in a runnable state (no half-broken intermediates).
- Prefer the simplest design. Do not over-engineer.
- If a decision requires input from the user, ask — don't assume.
