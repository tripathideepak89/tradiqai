# Dividend Radar Engine (DRE) — TradiqAI Integration Guide

## Files Delivered

| File | Purpose |
|------|---------|
| `dividend_ingestion.py` | NSE / BSE / MoneyControl fetcher + DB upsert |
| `dividend_scoring.py`   | DRE score engine + entry/trap signals |
| `dividend_backtest.py`  | Full S1/S2/S3 backtest with stats |
| `dividend_scheduler.py` | APScheduler 6:30 AM + Telegram alerts + FastAPI routes |
| `dre_migrations.sql`    | PostgreSQL tables, indexes, views |

---

## Step 1 — Run Migrations (Supabase SQL Editor)

Open your Supabase project → SQL Editor → paste `dre_migrations.sql` → Run.

Creates:
- `corporate_actions_dividends`  — raw dividend data
- `dividend_scores`              — DRE scores
- `dividend_backtest_trades`     — backtest results
- Views: `vw_dividend_radar`, `vw_dre_entry_signals`, `vw_backtest_summary`

---

## Step 2 — Install New Dependencies

```bash
pip install yfinance apscheduler beautifulsoup4
# (requests, psycopg2 are already in your requirements.txt)
```

Add to `requirements.txt`:
```
yfinance>=0.2.36
apscheduler>=3.10.4
beautifulsoup4>=4.12.0
```

---

## Step 3 — Drop Files into TradiqAI Root

```
tradiqai/
├── dividend_ingestion.py    ← NEW
├── dividend_scoring.py      ← NEW
├── dividend_backtest.py     ← NEW
├── dividend_scheduler.py    ← NEW
├── api.py                   ← MODIFY (add 3 lines)
├── main.py                  ← MODIFY (add 3 lines)
├── config.py                (no changes)
├── database.py              (no changes)
...
```

---

## Step 4 — Integrate with main.py

Add 3 lines to your existing `main.py`:

```python
# At the top of main.py, add:
from dividend_scheduler import DividendRadarScheduler

# Inside your main() or startup function, add:
radar = DividendRadarScheduler()
radar.start_background()   # non-blocking, runs at 6:30 AM IST
```

That's it. The DRE runs completely independently of your existing trading logic.

---

## Step 5 — Integrate with api.py (FastAPI)

Add 2 lines to your existing `api.py`:

```python
from dividend_scheduler import register_dre_routes

# After creating your FastAPI `app`, add:
register_dre_routes(app, get_db)   # get_db = your existing DB dependency
```

This adds 3 new API endpoints:
- `GET  /api/dividends/upcoming`   — all upcoming dividends with DRE scores
- `GET  /api/dividends/signals`    — only stocks with active entry signals
- `POST /api/dividends/refresh`    — manually trigger a DRE scan

---

## Step 6 — Test Manually

```bash
# Test one pipeline run immediately
python dividend_scheduler.py --once

# Test NSE fetcher only
python dividend_ingestion.py

# Test scoring only
python dividend_scoring.py

# Test backtest
python dividend_backtest.py
```

---

## Step 7 — Deploy

The DRE scheduler (`start_background()`) runs inside your existing process.
No new services or containers needed.

If you want to run it as a standalone service:
```bash
# Add to your Procfile:
dre: python dividend_scheduler.py

# Or systemd (see systemd/ folder pattern you already use):
# ExecStart=/path/to/venv/bin/python dividend_scheduler.py
```

---

## Environment Variables (already in your .env)

| Variable | Used By |
|----------|---------|
| `DATABASE_URL` | All DB connections |
| `TELEGRAM_BOT_TOKEN` | Alert sending |
| `TELEGRAM_CHAT_ID` | Alert sending |

No new env vars needed.

---

## Data Flow

```
6:30 AM IST
    │
    ▼
DividendIngestionService
    ├── NSEFetcher.fetch()          ← Primary (session cookie required)
    ├── BSEFetcher.fetch()          ← Fallback + enriches payment_date
    └── MoneyControlFetcher.fetch() ← Validation only
    │
    ▼
merge_and_deduplicate()
    │   Key: (symbol_dedup_key, ex_date, dividend_amount_rounded)
    │   Priority: NSE > BSE > MC
    │
    ▼
corporate_actions_dividends  (DB upsert)
    │
    ▼
DividendScoringEngine.score_all()
    ├── _fetch_price_data()         ← yfinance (.NS suffix)
    ├── _fetch_fundamentals()       ← yfinance (ROE, D/E, div history)
    ├── _score_yield()              ← 0–25
    ├── _score_consistency()        ← 0–20
    ├── _score_growth()             ← 0–15
    ├── _score_financials()         ← 0–20
    └── _score_technicals()         ← 0–20
    │
    ▼
dividend_scores  (DB upsert)
    │
    ▼
TelegramAlerter
    ├── send_dre_alert()   ← one per entry signal stock
    └── send_daily_summary()
```

---

## NSE Session Note (Important)

NSE blocks API calls without a valid browser session cookie.
The NSEFetcher automatically:
1. Hits `https://www.nseindia.com` (gets base cookies)
2. Hits the corporate actions page (refreshes cookies)
3. Calls the JSON API

Session is cached for 30 minutes. If NSE returns empty, it forces a re-init.

If NSE fails consistently in production, fall back to their CSV download:
```
https://www.nseindia.com/api/corporates-corporateActions?index=equities&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY&csv=true
```
Parse the CSV response instead of JSON.

---

## Backtest Quick Start

```python
from dividend_backtest import DividendBacktester, BacktestConfig

bt = DividendBacktester(db_conn=your_conn)

# Load 5 years of dividend events from DB
events = bt.load_events_from_db(start_year=2020)

# Run Strategy 1: buy 10 days before, exit 1 day before ex-date
cfg = BacktestConfig(
    strategy          = "S1",
    entry_n           = 10,
    exit_offset       = -1,
    use_trend_filter  = True,
    use_yield_filter  = True,
    min_yield         = 2.0,
)
trades = bt.run(events, cfg)
bt.print_summary(trades)
bt.export_csv(trades, "dre_backtest_S1.csv")

# Robustness check: all N × offset combinations
rob_df = bt.robustness_check(events)
print(rob_df.to_string())
```

---

## Dashboard API Response Format

`GET /api/dividends/upcoming` returns:
```json
[
  {
    "symbol":           "ITC",
    "name":             "ITC Ltd",
    "exchange":         "NSE",
    "dividend_amount":  6.5,
    "dividend_type":    "Final",
    "ex_date":          "2026-03-12",
    "record_date":      "2026-03-13",
    "payment_date":     null,
    "days_to_ex":       14,
    "dre_score":        82,
    "yield_pct":        3.5,
    "category":         "Strong Buy",
    "is_trap":          false,
    "entry_signal":     true,
    "trend":            "Strong",
    "price":            462.0,
    "above_20dma":      true,
    "above_50dma":      true,
    "above_200dma":     true,
    "roe":              22.0,
    "de":               0.1,
    "score_yield":      20,
    "score_consistency":20,
    "score_growth":     15,
    "score_financial":  20,
    "score_technical":  10,
    "entry_zone_low":   457.0,
    "entry_zone_high":  466.6
  }
]
```

Your existing DRE React dashboard (dividend-radar-engine-v2.jsx) already
expects this exact shape — just replace the `MOCK_DATA` array with
a `fetch('/api/dividends/upcoming')` call.

---

## Legal / Rate Limit Notes

- NSE: max 1 call per day (scheduler). Do not poll during market hours.
- BSE: same as NSE. 1 call per day is respectful.
- MoneyControl: scraping only — use only for validation, not primary data.
- Cache results in DB. Never hammer exchanges repeatedly.
- Your existing `governance.py` already tracks this — add DRE run logs there.
