---
name: "Implement"
description: "Execute a TradiqAI implementation plan step-by-step with todo tracking, per-step verification, safe git commits, and a completion summary including Railway deploy guidance."
---

# Implement Skill — TradiqAI

Execute the plan precisely — one step at a time, verifying before moving on.

## Pre-flight Checklist

Before starting, confirm:
- [ ] Plan from `/plan` is in context
- [ ] Understand which process is affected: `main.py`, `dashboard.py`, or both
- [ ] Know which data store is used: Supabase or SQLAlchemy
- [ ] Know if a Railway redeploy is required

## Process

1. **Create a todo list** using TodoWrite — one item per plan step. Mark complete as you go.

2. **Execute step by step:**
   - Read the file before editing it (always)
   - Make only the changes the plan specifies
   - Do not refactor surrounding code, add comments, or clean up unrelated things
   - After each step: verify syntax is valid, imports resolve, logic is correct

3. **TradiqAI-specific verification per step:**

   *Adding a new API route:*
   - Route registered in `dashboard.py` inside try/except block?
   - Auth dependency `Depends(get_current_user)` present if protected?
   - Test: `curl https://tradiqai.com/api/<route>` or open in browser

   *Changing a strategy:*
   - Time filter still respected (`TimeFilter.can_enter_new_trade()`)?
   - Rejected trade written on signal rejection (`order_manager.record_rejected_trade()`)?
   - Test: check `/audit/rejected-trades` during 09:45–11:30 or 13:45–14:45 IST

   *Changing quote fetching:*
   - Using existing `quote_cache` in `dashboard.py`?
   - Batch size ≤ 5, delay between batches?
   - Market hours gate (`is_market_open()`) applied?

   *Changing `main.py` or trading bot:*
   - After deploy: check `/api/bot-status` — `bot_running: true` + recent `heartbeat`?
   - Scan logs: `[TRADING BOT] Starting main.py...` in Railway logs?

   *Changing templates:*
   - Auth uses `localStorage.getItem('access_token')` → `Authorization: Bearer <token>`?
   - API calls go to `/api/...` (not `/auth/me` — known past bug)?
   - IST timezone displayed correctly to user?

   *Changing Dockerfile / start.sh / .dockerignore:*
   - `start.sh` NOT in `.dockerignore`?
   - Uses `python3` not `python3.11`?
   - `set +e` in the trading bot subshell?

4. **On failure or surprise:** Stop. Diagnose. Explain what you found. Propose a plan adjustment. Do NOT retry the same failing approach.

5. **Commit when a logical unit is complete:**
   ```
   git add <specific files>
   git commit -m "type: description of what and why"
   # Do NOT commit .env, *.key, credentials files
   # Do NOT use --no-verify
   ```

6. **Completion summary:**

```
## Implementation Complete: <feature name>

### Changes Made
- `file.py:line` — what changed and why
- (one bullet per file)

### Not Done / Deferred
- Anything skipped with reason

### How to Verify
1. Exact manual test steps (include IST time if market-hours dependent)
2. Railway log lines to confirm: "[TRADING BOT] ..." / specific INFO messages
3. Supabase table to check (table name + what to look for)
4. API endpoint to hit: GET/POST https://tradiqai.com/api/<route>

### Railway Deploy
- [ ] Push triggers auto-deploy (code/template only changes)
- [ ] Docker rebuild needed — watch Railway build logs (~3-5 min)
- [ ] New env vars to set in Railway dashboard
- [ ] Run `/api/bot-status` after deploy to confirm bot is alive

### Follow-up
- Technical debt introduced
- Recommended next steps
```

## Hard Rules
- **Read before editing** — always use the Read tool first
- **Minimal changes** — only what the plan requires
- **No speculative improvements** — don't touch unrelated code
- **Stop on blockers** — surface errors immediately, don't retry blindly
- **One file at a time** where possible
- **Never commit secrets** — `.env`, `*.key`, API tokens
- **Never skip hooks** — don't use `--no-verify`
