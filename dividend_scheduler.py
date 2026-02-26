"""
dividend_scheduler.py
=====================
TradiqAI — Dividend Radar Engine
Daily scheduler (6:30 AM IST) + Telegram alert engine.

Wires together:
  DividendIngestionService  →  DividendScoringEngine  →  Telegram/DB alerts

Drop this file in your TradiqAI root directory.
It uses the same DATABASE_URL and TELEGRAM_* env vars your existing system uses.

Usage (standalone):
    python dividend_scheduler.py

Usage (integrated with your existing main.py / monitoring.py):
    from dividend_scheduler import DividendRadarScheduler
    radar = DividendRadarScheduler()
    radar.start()           # starts APScheduler job
    # OR run once immediately:
    radar.run_once()
"""

import os
import json
import logging
import textwrap
from datetime import datetime

try:
    import psycopg2  # type: ignore[import]
    _psycopg = psycopg2
except ImportError:
    import psycopg as psycopg2  # psycopg v3 (installed as psycopg[binary])
    _psycopg = psycopg2
import requests

# Import DRE modules (same directory)
from dividend_ingestion import DividendIngestionService
from dividend_scoring   import DividendScoringEngine

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  TELEGRAM ALERT
# ─────────────────────────────────────────────

class TelegramAlerter:
    """
    Reuses the same TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
    already configured in your TradiqAI .env
    """

    def __init__(self):
        self.token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)
        if not self.enabled:
            logger.warning("Telegram not configured — alerts will be logged only.")

    def send(self, message: str) -> bool:
        if not self.enabled:
            logger.info(f"[ALERT (no Telegram)]\n{message}")
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id":    self.chat_id,
            "text":       message,
            "parse_mode": "HTML",
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error(f"Telegram send failed: {exc}")
            return False

    def send_dre_alert(self, stock: dict) -> bool:
        """
        Send formatted Dividend Radar alert for a single stock.
        Matches the alert format from your DRE spec.
        """
        cat_emoji = {
            "Strong Buy": "🟢",
            "Watchlist":  "🟡",
            "Moderate":   "🟠",
            "Ignore":     "🔴",
        }.get(stock.get("category", ""), "⚪")

        trap_line = "\n⚠️ <b>DIVIDEND TRAP WARNING</b> — Avoid entry." if stock.get("is_trap") else ""
        signal_line = "\n🎯 <b>ENTRY SIGNAL ACTIVE</b>" if stock.get("entry_signal") else ""

        entry_zone = ""
        if stock.get("entry_zone_low") and stock.get("entry_zone_high"):
            entry_zone = f"\n💰 Suggested Entry Zone: ₹{stock['entry_zone_low']} – ₹{stock['entry_zone_high']}"

        score_bar = self._score_bar(stock.get("dre_score", 0))

        msg = textwrap.dedent(f"""
🔔 <b>Dividend Radar Alert</b>
━━━━━━━━━━━━━━━━━━━━━

📌 <b>Stock:</b>      {stock.get('symbol', stock.get('name', 'N/A'))}
🏢 <b>Exchange:</b>   {stock.get('exchange', 'NSE')}
📅 <b>Ex-Date:</b>    {stock.get('ex_date', 'N/A')}
⏳ <b>Days Left:</b>  {stock.get('days_to_ex', '?')} days
💵 <b>Dividend:</b>   ₹{stock.get('dividend_amount', 0):.2f} ({stock.get('dividend_type', 'Dividend')})
📈 <b>Yield:</b>      {stock.get('yield_pct', 0):.2f}%
🎯 <b>DRE Score:</b>  {stock.get('dre_score', 0)}/100  {score_bar}
{cat_emoji} <b>Category:</b>  {stock.get('category', 'N/A')}
📊 <b>Trend:</b>      {stock.get('trend', 'N/A')}
{entry_zone}{trap_line}{signal_line}

<i>Source: {stock.get('source','NSE')} • TradiqAI DRE</i>
        """).strip()

        return self.send(msg)

    def send_daily_summary(self, scored: list[dict]) -> bool:
        """Send a daily digest of all scored stocks."""
        strong_buys    = [s for s in scored if s.get("category") == "Strong Buy"]
        entry_signals  = [s for s in scored if s.get("entry_signal")]
        traps          = [s for s in scored if s.get("is_trap")]

        lines = [
            "📡 <b>Dividend Radar Daily Summary</b>",
            f"━━━━━━━━━━━━━━━━━━━━━━━",
            f"📅 {datetime.now().strftime('%d %b %Y')}",
            f"",
            f"📊 <b>Total dividends (next 14d):</b> {len(scored)}",
            f"🟢 <b>Strong Buy (80+):</b>           {len(strong_buys)}",
            f"🎯 <b>Entry Signals:</b>               {len(entry_signals)}",
            f"⚠️ <b>Trap Warnings:</b>               {len(traps)}",
            "",
        ]

        if entry_signals:
            lines.append("🎯 <b>Active Entry Signals:</b>")
            for s in entry_signals[:5]:  # cap at 5 per message
                lines.append(
                    f"  • <b>{s.get('symbol','?')}</b>  "
                    f"Score={s.get('dre_score')}  "
                    f"Yield={s.get('yield_pct',0):.1f}%  "
                    f"Ex={s.get('ex_date','?')}"
                )

        if strong_buys and not entry_signals:
            lines.append("🟢 <b>Strong Buy Stocks:</b>")
            for s in strong_buys[:5]:
                lines.append(
                    f"  • <b>{s.get('symbol','?')}</b>  "
                    f"Score={s.get('dre_score')}  "
                    f"Yield={s.get('yield_pct',0):.1f}%"
                )

        if traps:
            lines.append("")
            lines.append("⚠️ <b>Avoid (Dividend Traps):</b>")
            for t in traps:
                lines.append(f"  • {t.get('symbol','?')}  Yield={t.get('yield_pct',0):.1f}%  ⬇️ Downtrend")

        lines.append("")
        lines.append("<i>TradiqAI Dividend Radar Engine</i>")

        return self.send("\n".join(lines))

    @staticmethod
    def _score_bar(score: int) -> str:
        filled = round(score / 10)
        return "▓" * filled + "░" * (10 - filled)


# ─────────────────────────────────────────────
#  MAIN SCHEDULER
# ─────────────────────────────────────────────

class DividendRadarScheduler:
    """
    Orchestrates the full DRE pipeline on a daily schedule.

    Integrates with your existing TradiqAI:
      • Uses DATABASE_URL from .env (same as your database.py)
      • Uses TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID (same as monitoring.py)
      • Writes to corporate_actions_dividends + dividend_scores tables
    """

    def __init__(self):
        self.db_url   = os.environ.get("DATABASE_URL", "")
        self.alerter  = TelegramAlerter()
        self._conn    = None

    def _get_conn(self):
        """Get (or reopen) DB connection."""
        try:
            if self._conn and not self._conn.closed:
                return self._conn
            self._conn = psycopg2.connect(self.db_url)
            return self._conn
        except Exception as exc:
            logger.error(f"DB connection failed: {exc}")
            return None

    def run_once(self) -> list[dict]:
        """
        Execute full DRE pipeline once.
        Called by scheduler at 6:30 AM, or manually for testing.

        Pipeline:
          1. Fetch dividends from NSE/BSE/MC
          2. Deduplicate + upsert to DB
          3. Score all records
          4. Save scores to DB
          5. Send Telegram alerts for entry signals
          6. Send daily summary
        """
        logger.info("═" * 55)
        logger.info("DRE Pipeline started")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
        logger.info("═" * 55)

        conn = self._get_conn()
        if not conn:
            logger.error("DRE: Cannot run — no DB connection.")
            return []

        # ── Step 1 & 2: Ingest (upsert any new records) ─────────────
        ingestion_svc = DividendIngestionService(conn, window_days=14)
        ingestion_svc.ensure_table()
        fetched = ingestion_svc.run_full_ingestion()
        if fetched:
            logger.info(f"DRE: {len(fetched)} new dividend records upserted.")
        else:
            logger.warning(
                "DRE: External sources returned 0 records (NSE/BSE may be blocked). "
                "Rescoring existing DB records with fresh prices."
            )

        # Always read ALL upcoming dividends from DB so existing records
        # get rescored with fresh Kite price data even when ingestion returns 0.
        dividend_records = ingestion_svc.get_upcoming_dividends()

        if not dividend_records:
            logger.warning("DRE: No upcoming dividends in DB for next 14 days.")
            self.alerter.send("📡 DRE: No upcoming dividends in DB for next 14 days.")
            return []

        logger.info(f"DRE: Scoring {len(dividend_records)} upcoming dividends from DB.")

        # ── Step 3 & 4: Score ───────────────────
        scoring_engine = DividendScoringEngine(conn)
        scored         = scoring_engine.score_all(dividend_records)
        scoring_engine.save_scores_to_db(scored)

        # ── Step 5: Individual entry signal alerts ─
        entry_signals = [s for s in scored if s.get("entry_signal")]
        logger.info(f"DRE: {len(entry_signals)} entry signals generated.")
        for stock in entry_signals:
            self.alerter.send_dre_alert(stock)

        # ── Step 6: Daily summary ───────────────
        self.alerter.send_daily_summary(scored)

        # ── Logging ─────────────────────────────
        self._log_run_stats(scored)

        logger.info("DRE Pipeline complete.")
        return scored

    def _log_run_stats(self, scored: list[dict]):
        """Log a compact summary to console."""
        cats = {"Strong Buy": 0, "Watchlist": 0, "Moderate": 0, "Ignore": 0}
        for s in scored:
            cats[s.get("category", "Ignore")] = cats.get(s.get("category", "Ignore"), 0) + 1

        logger.info(
            f"DRE Results: Total={len(scored)} | "
            f"Strong Buy={cats['Strong Buy']} | "
            f"Watchlist={cats['Watchlist']} | "
            f"Traps={sum(1 for s in scored if s.get('is_trap'))} | "
            f"Signals={sum(1 for s in scored if s.get('entry_signal'))}"
        )

    def start(self):
        """
        Start APScheduler for 6:30 AM IST daily run.
        IST = UTC+5:30 → 6:30 AM IST = 1:00 AM UTC
        """
        try:
            from apscheduler.schedulers.blocking import BlockingScheduler
            from apscheduler.triggers.cron      import CronTrigger

            scheduler = BlockingScheduler(timezone="Asia/Kolkata")
            scheduler.add_job(
                func     = self.run_once,
                trigger  = CronTrigger(hour=6, minute=30, timezone="Asia/Kolkata"),
                id       = "dividend_radar_daily",
                name     = "DRE Daily Scan",
                replace_existing = True,
                misfire_grace_time = 600,   # allow up to 10min late start
            )

            logger.info("DRE Scheduler started. Next run: 6:30 AM IST daily.")
            logger.info("Press Ctrl+C to stop.")

            # Run immediately on startup too
            logger.info("Running initial scan now…")
            self.run_once()

            scheduler.start()

        except ImportError:
            logger.error("APScheduler not installed. Run: pip install apscheduler")
            raise
        except (KeyboardInterrupt, SystemExit):
            logger.info("DRE Scheduler stopped.")

    def start_background(self):
        """
        Start in background mode (non-blocking).
        Use this when integrating with your existing main.py loop.

        In main.py:
            from dividend_scheduler import DividendRadarScheduler
            radar = DividendRadarScheduler()
            radar.start_background()
            # your existing main loop continues…
        """
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron         import CronTrigger

            self._scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
            self._scheduler.add_job(
                func     = self.run_once,
                trigger  = CronTrigger(hour=6, minute=30, timezone="Asia/Kolkata"),
                id       = "dividend_radar_daily",
                replace_existing = True,
            )
            self._scheduler.start()
            logger.info("DRE background scheduler started (6:30 AM IST).")
            return self._scheduler

        except ImportError:
            logger.error("APScheduler not installed.")
            raise

    def stop(self):
        if hasattr(self, "_scheduler"):
            self._scheduler.shutdown(wait=False)
            logger.info("DRE Scheduler stopped.")


# ─────────────────────────────────────────────
#  API ENDPOINTS  (FastAPI — plug into your api.py)
# ─────────────────────────────────────────────

def register_dre_routes(app, get_db):
    """
    Register DRE API endpoints with your existing FastAPI app.

    In your api.py, add:
        from dividend_scheduler import register_dre_routes
        register_dre_routes(app, get_db)

    Then your frontend / dashboard can call:
        GET /api/dividends/upcoming
        GET /api/dividends/signals
        POST /api/dividends/refresh
    """
    try:
        from fastapi import Depends
        from fastapi.responses import JSONResponse
    except ImportError:
        logger.warning("FastAPI not available — skipping route registration.")
        return

    import decimal as _decimal
    import datetime as _datetime

    def _serialize(obj):
        """Convert psycopg2 non-JSON types to JSON-safe Python types."""
        if isinstance(obj, _decimal.Decimal):
            return float(obj)
        if isinstance(obj, (_datetime.date, _datetime.datetime)):
            return obj.isoformat()
        return obj

    def _rows_to_json(cols, rows):
        return [{c: _serialize(v) for c, v in zip(cols, r)} for r in rows]

    @app.get("/api/dividends/upcoming")
    def get_upcoming_dividends(db=Depends(get_db)):
        """Return upcoming dividends with DRE scores for the Radar UI."""
        sql = """
            SELECT
                d.symbol, d.name, d.exchange, d.dividend_amount, d.dividend_type,
                d.ex_date, d.record_date, d.payment_date,
                s.dre_score, s.yield_pct, s.category, s.trend,
                s.is_trap, s.entry_signal, s.days_to_ex,
                s.entry_zone_low, s.entry_zone_high,
                s.score_yield, s.score_consistency, s.score_growth,
                s.score_financial, s.score_technical
            FROM   corporate_actions_dividends d
            LEFT JOIN dividend_scores s
                ON s.symbol = d.symbol AND s.ex_date = d.ex_date
            WHERE  d.ex_date >= CURRENT_DATE
              AND  d.ex_date <= CURRENT_DATE + INTERVAL '14 days'
            ORDER  BY COALESCE(s.dre_score, 0) DESC;
        """
        with db.cursor() as cur:
            cur.execute(sql)
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
        return JSONResponse(_rows_to_json(cols, rows))

    @app.get("/api/dividends/signals")
    def get_entry_signals(db=Depends(get_db)):
        """Return only stocks with active entry signals."""
        sql = """
            SELECT *
            FROM   dividend_scores
            WHERE  entry_signal = TRUE
              AND  ex_date >= CURRENT_DATE
            ORDER  BY dre_score DESC;
        """
        with db.cursor() as cur:
            cur.execute(sql)
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
        return JSONResponse(_rows_to_json(cols, rows))

    @app.post("/api/dividends/refresh")
    def trigger_refresh():
        """Manually trigger a DRE pipeline run (admin use)."""
        try:
            scheduler = DividendRadarScheduler()
            scored    = scheduler.run_once()
            return JSONResponse({
                "status":        "ok",
                "records_scored": len(scored),
                "entry_signals": sum(1 for s in scored if s.get("entry_signal")),
            })
        except Exception as exc:
            return JSONResponse({"status": "error", "message": str(exc)}, status_code=500)

    logger.info("DRE API routes registered: /api/dividends/upcoming, /signals, /refresh")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import logging
    from dotenv import load_dotenv

    load_dotenv()  # loads your existing .env file

    logging.basicConfig(
        level  = logging.INFO,
        format = "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt= "%Y-%m-%d %H:%M:%S",
    )

    radar = DividendRadarScheduler()

    import sys
    if "--once" in sys.argv:
        # Run once and exit (useful for cron job alternative)
        scored = radar.run_once()
        print(f"\nDRE complete: {len(scored)} stocks scored.")
        sys.exit(0)
    else:
        # Start blocking scheduler
        radar.start()
