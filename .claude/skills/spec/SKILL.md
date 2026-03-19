---
name: "Spec"
description: "Write a clear feature specification for TradiqAI. Covers problem, goals, scope, user stories, and open questions before any research or code is written."
---

# Spec Skill — TradiqAI

Turn a rough idea into a precise, unambiguous feature spec for the TradiqAI trading platform.

## Project Architecture to Keep in Mind

**Two processes, one Railway container:**
- `main.py` — trading bot (executes trades, scans signals, runs strategies)
- `dashboard.py` — FastAPI web server (UI, WebSocket, REST APIs)

**Two data stores:**
- Supabase/PostgreSQL — auth, trades display, dividend data, users table
- SQLAlchemy (same Postgres in prod, SQLite locally) — Trade model, analytics, rejected_trades

**Key patterns:**
- Auth: `Depends(get_current_user)` from `tradiqai_supabase_auth` on protected routes
- Capital: single source of truth in `live_capital.py` → `set_live_capital()` / `get_live_capital()`
- Trading windows: **09:45–11:30 IST** and **13:45–14:45 IST** only (enforced by `TimeFilter`)
- Broker: Groww via `brokers/groww.py` — rate-limited, don't exceed ~5 req/s

**Key files by concern:**
- Strategies: `strategies/strong_dip.py`, `strategies/swing.py`, `strategies/intraday.py`, etc.
- Broker: `brokers/groww.py`, `brokers/zerodha.py`, `brokers/factory.py`
- Data ingestion: `dividend_ingestion.py`, `dividend_scheduler.py`
- APIs: `api_portfolio.py`, `api_audit.py`, `api_sdoe.py`
- Templates: `templates/*.html`
- Config: `config.py` (reads from env vars), `start.sh`, `Dockerfile`

## Process

1. Ask 1–3 clarifying questions if the requirement is too vague. Otherwise proceed.

2. Write the spec using this structure:

```
## Feature: <name>

### Problem
What is broken or missing? Why does it matter for trading / the user experience?

### Goals
- Measurable outcomes (e.g. "rejected trades visible within 5s of signal rejection")

### Non-Goals
- What is explicitly out of scope

### Affected Systems
- [ ] dashboard.py (web server / API routes)
- [ ] main.py (trading bot / scan loop)
- [ ] A strategy: strategies/<name>.py
- [ ] Broker adapter: brokers/groww.py
- [ ] Supabase tables (which tables?)
- [ ] SQLAlchemy models: models.py
- [ ] A page template: templates/<name>.html
- [ ] Data ingestion: dividend_ingestion.py / dividend_scheduler.py
- [ ] Deployment: Dockerfile / start.sh / Railway config

### User Stories
- As a trader, I want to <action> so that <outcome>

### Functional Requirements
1. Use "must" — concrete, independently verifiable behaviours
2. Include time constraints where relevant (IST timezone, market hours)

### Technical Constraints
- IST timezone for all time-sensitive logic (use `now_ist()` from `utils/timezone.py`)
- No blocking I/O in async FastAPI handlers
- Groww rate limit: batch requests, don't fire >5 concurrently
- Supabase vs SQLAlchemy: which is source of truth for this feature?
- Market hours enforcement: does this run inside or outside trading windows?

### Open Questions
- Unresolved decisions that must be answered before or during implementation
```

3. Suggest: "Run `/research` to investigate unknowns, or `/plan` if the spec is clear enough."

## Rules
- Do NOT design the solution — that's for `/plan`
- Do NOT read code unless asked to reference existing behaviour
- Use "must" / "will" / "shall" — not "should" / "nice to have"
- Keep scope tight — a good spec says "no" clearly
