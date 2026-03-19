---
name: "Plan"
description: "Design a step-by-step implementation plan for a TradiqAI feature. Covers architecture decisions, exact files to change, ordered steps, test strategy, and Railway deploy impact."
---

# Plan Skill — TradiqAI

Design the implementation — do NOT write code yet. A good plan makes the coding step mechanical.

## TradiqAI-Specific Design Rules

Before writing the plan, verify these constraints are satisfied:

1. **Async safety** — FastAPI handlers (`dashboard.py`) must never block. Use `asyncio.wait_for()`, `run_in_executor()` for sync code, or `aiohttp` for HTTP.
2. **Process isolation** — `main.py` and `dashboard.py` are separate OS processes. They cannot share Python objects or in-process caches. Shared state must go through Supabase, SQLAlchemy DB, or a file.
3. **Data store consistency** — Decide: Supabase (supabase-py client) OR SQLAlchemy — not both for the same data. See MEMORY.md for which page uses which.
4. **Auth on new routes** — All protected routes need `Depends(get_current_user)`. Register routers in `dashboard.py` inside a try/except block.
5. **Timezone** — All datetimes must use `now_ist()` / `today_ist()` from `utils/timezone.py`. Never use `datetime.now()` or `datetime.utcnow()`.
6. **Groww rate limits** — Any new quote fetching must use the existing `quote_cache` in `dashboard.py` and respect batch size (5) + delay (500ms). Do not add concurrent Groww calls outside this pattern.
7. **Railway deploy** — Any change to `start.sh`, `Dockerfile`, or `.dockerignore` must be noted explicitly in the plan. `start.sh` must NOT be in `.dockerignore`.
8. **No breaking the bot** — Changes to `main.py`, `order_manager.py`, or strategies must not interrupt the scan loop. Prefer additive changes.

## Process

1. Gather inputs — need spec (from `/spec`) and research (from `/research`). Ask if missing.

2. Design the solution — think before writing:
   - Simplest design that satisfies all requirements?
   - Reuse existing patterns vs. new code?
   - Order of changes to keep system runnable at every step?
   - Does this need a Railway redeploy? (changes to Dockerfile, start.sh, requirements.txt)

3. Write the plan:

```
## Implementation Plan: <feature name>

### Approach
2-4 sentences: overall strategy, key decisions, why this approach.

### Architecture Decisions
- Decision: <what>
  Reason: <why this vs alternatives>
  (one per significant decision — data store choice, sync vs async, caching strategy, etc.)

### Files to Change
| File | Change | Description |
|------|--------|-------------|
| dashboard.py | Modify | Add route X, register router Y |
| strategies/foo.py | Modify | Add signal condition Z |
| templates/bar.html | Modify | Add UI for feature |
| models.py | Modify | Add column / new model |
| requirements.txt | Modify | Add package (triggers Railway rebuild) |
| Dockerfile / start.sh | Modify | ⚠️ Requires Railway redeploy |

### Implementation Steps
Each step must leave the system in a runnable state.

1. **<Step name>** — why first
   - Concrete sub-task
   - Expected outcome to verify before proceeding

2. **<Step name>**
   - ...

### Verification
- Manual test: exact steps to confirm it works end-to-end (include IST time if market-hours dependent)
- Check Railway logs for: (specific log lines to look for)
- Check `/api/bot-status` if main.py is involved
- Supabase table to inspect: (table name, query)

### Risks & Mitigations
- Risk: <what could go wrong>
  Mitigation: <how to handle it>

### Railway Deploy Impact
- [ ] Requires Docker rebuild (changes to Dockerfile, requirements.txt, start.sh, .dockerignore)
- [ ] Environment variable changes needed
- [ ] Database migration needed
- [ ] No redeploy needed (Python/template changes only — Railway auto-deploys)
```

4. Ask: "Does this look right? Say `/implement` to start, or tell me what to adjust."

## Rules
- No implementation code in the plan
- Each step must leave the codebase runnable
- Prefer simplest design — do not over-engineer
- Flag any step that requires a Railway redeploy explicitly
- If a decision requires user input, ask — don't assume
