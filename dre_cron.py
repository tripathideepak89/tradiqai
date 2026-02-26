"""
dre_cron.py
===========
TradiqAI — Dividend Radar Engine local cron runner

Run this script daily from your LOCAL machine (or any non-datacenter IP)
where NSE/BSE APIs are accessible.  It fetches fresh dividend data, upserts
it into Supabase, then calls the Railway API to trigger scoring.

Usage:
    python dre_cron.py

Schedule (Windows Task Scheduler):
    Action:  python C:/Users/dtrid8/development/autotrade-ai/dre_cron.py
    Trigger: Daily, 6:00 AM

Schedule (Linux/Mac cron):
    0 6 * * 1-5 /usr/bin/python3 /path/to/dre_cron.py

Requires (already in your project venv):
    psycopg[binary]  requests  beautifulsoup4  python-dotenv
"""

import logging
import os
import sys
import time

# ── Load .env so DATABASE_URL is available ───────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional; set DATABASE_URL in env instead

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dre_cron")

# ── Config ────────────────────────────────────────────────────────────
DATABASE_URL       = os.environ.get("DATABASE_URL", "")
RAILWAY_API_BASE   = "https://tradiqai.com"       # Production URL
WINDOW_DAYS        = 14                            # Days ahead to scan


def main():
    if not DATABASE_URL:
        logger.error("DATABASE_URL not set. Add it to .env or environment.")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("DRE Local Cron — starting")
    logger.info("=" * 60)

    # ── Connect to Supabase ──────────────────────────────────────────
    try:
        try:
            import psycopg2 as pg
        except ImportError:
            import psycopg as pg          # psycopg v3

        conn = pg.connect(DATABASE_URL)
        logger.info("DB: connected to Supabase")
    except Exception as exc:
        logger.error(f"DB connection failed: {exc}")
        sys.exit(1)

    # ── Run ingestion (from your local/residential IP) ───────────────
    try:
        from dividend_ingestion import DividendIngestionService
        svc = DividendIngestionService(conn, window_days=WINDOW_DAYS)
        svc.ensure_table()
        records = svc.run_full_ingestion()
        logger.info(f"Ingestion: {len(records)} dividend records upserted")
    except Exception as exc:
        logger.error(f"Ingestion failed: {exc}")
        conn.close()
        sys.exit(1)

    conn.close()

    if not records:
        logger.warning("No dividends found in the next 14 days — nothing to score.")
        sys.exit(0)

    # ── Trigger Railway to score + alert ─────────────────────────────
    # Small delay to ensure DB write is committed before Railway reads it
    time.sleep(2)

    try:
        import requests
        resp = requests.post(
            f"{RAILWAY_API_BASE}/api/dividends/refresh",
            timeout=60,
        )
        data = resp.json()
        logger.info(
            f"Railway scored: {data.get('records_scored', '?')} stocks, "
            f"{data.get('entry_signals', '?')} entry signals"
        )
    except Exception as exc:
        logger.warning(f"Railway refresh call failed: {exc}")
        logger.info("Data is in Supabase — Railway will pick it up at next scheduled run.")

    logger.info("DRE Local Cron — done")


if __name__ == "__main__":
    main()
