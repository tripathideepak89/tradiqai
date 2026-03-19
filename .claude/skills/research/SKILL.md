---
name: "Research"
description: "Investigate the TradiqAI codebase, Supabase schema, broker APIs, or strategies to answer spec unknowns. Read-only — produces a summary of current state, risks, and remaining unknowns."
---

# Research Skill — TradiqAI

Investigate and report — do NOT write code. Answer the open questions in a spec and surface risks before planning.

## Key Areas to Investigate by Topic

**Adding/changing an API route:**
- Where is the router registered in `dashboard.py`? (all in try/except blocks near bottom)
- Auth pattern: `Depends(get_current_user)` from `tradiqai_supabase_auth` required?
- Does it read from Supabase or SQLAlchemy? (different clients — `supabase.table()` vs `self.db.query()`)

**Changing trading logic:**
- Which strategy file in `strategies/`? Base class in `strategies/base.py`
- Time filter: `TimeFilter.can_enter_new_trade()` — windows are 09:45–11:30 and 13:45–14:45 IST
- Signal flow: `main.py` scan loop → `order_manager.py` → `brokers/groww.py`
- Rejected trades written by `order_manager.py` → `rejected_trades` table via SQLAlchemy

**Changing a dashboard page:**
- Template in `templates/<page>.html` — uses `localStorage.getItem('access_token')` for auth
- API calls must go to `/api/...` (not `/auth/me` — that's a known past bug)
- Data source: check MEMORY.md table for which page reads from Supabase vs SQLAlchemy

**Broker / quote fetching:**
- `brokers/groww.py` — rate-limited; `QUOTE_CACHE_TTL = 240s` in `dashboard.py`
- Quote fetching gated to market hours (`is_market_open()`) to avoid 429s
- Batch size = 5, 500ms delay between batches

**Dividend / DRE:**
- `dividend_ingestion.py` — BSE fetcher with cookie session auth; `_normalise()` maps field names
- `dividend_scheduler.py` — runs at 6:30 AM IST daily; manual trigger via `POST /api/dividends/refresh`
- Tables: `corporate_actions_dividends`, `dividend_scores` (Supabase/Postgres only)

**Deployment:**
- `start.sh` runs both `main.py` (background loop) and `uvicorn dashboard:app` (foreground)
- `Dockerfile` builds from `python:3.13-slim`; `start.sh` must NOT be in `.dockerignore`
- Env vars: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `GROWW_API_KEY`, `GROWW_API_SECRET`

## Process

1. Read the spec / task. Extract every open question, unknown dependency, unclear constraint.

2. Investigate using tools — read files, grep for patterns, check git log for context:
   ```
   # Useful search patterns
   grep for route registration, model definitions, import chains
   Read relevant strategy/broker/template files
   git log --oneline -- <file>  for history on tricky files
   ```

3. Write the research summary:

```
## Research: <feature/task name>

### Current State
How does the relevant part of the system work today?
Key files, functions, data flows — be specific.

### Relevant Code
- `dashboard.py:488` — QUOTE_CACHE_TTL, quote_cache dict
- `brokers/groww.py:100` — connect(), _make_request()
- (cite exact file:line for everything important)

### Data Flow
For the affected feature, trace: trigger → processing → storage → display

### Dependencies & Integration Points
- Which modules import each other?
- Which Supabase tables are read/written?
- Which SQLAlchemy models are involved?
- Any external APIs (Groww, NSE, BSE, yfinance)?

### Risks & Gotchas
- Known past bugs in this area (check MEMORY.md)
- Race conditions between main.py and dashboard.py (they share Supabase but NOT in-process state)
- Async vs sync code mixing
- Timezone issues (always use now_ist(), today_ist() from utils/timezone.py)

### Answers to Open Questions
- Question from spec → Answer (cite source) or "still unknown"

### Remaining Unknowns
- What couldn't be resolved — needs decision during planning or implementation
```

4. Suggest: "Run `/plan` with the spec + this research summary."

## Rules
- Read-only — no code changes
- Cite exact file paths and line numbers
- Flag anything surprising or risky prominently
- Don't research tangents — stay focused on the spec's scope
