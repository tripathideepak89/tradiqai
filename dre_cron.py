"""
dre_cron.py
===========
TradiqAI — Dividend Radar Engine local cron runner

Run this daily from your LOCAL machine where NSE APIs are accessible.
Does the full pipeline locally: ingest → score → write scores to Supabase.
Railway just reads the pre-computed scores and serves them.

Usage:
    python dre_cron.py

Schedule (Windows Task Scheduler):
    Action:  python C:/Users/dtrid8/development/autotrade-ai/dre_cron.py
    Trigger: Daily, 6:00 AM

Schedule (Linux/Mac cron):
    0 6 * * 1-5 /usr/bin/python3 /path/to/dre_cron.py

Requires (already in your project venv):
    psycopg[binary]  requests  beautifulsoup4  yfinance  python-dotenv
"""

import logging
import os
import sys

# ── Load .env so DATABASE_URL + KITE_* env vars are available ─────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dre_cron")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
WINDOW_DAYS  = 14


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
            import psycopg as pg
        conn = pg.connect(DATABASE_URL)
        logger.info("DB: connected to Supabase")
    except Exception as exc:
        logger.error(f"DB connection failed: {exc}")
        sys.exit(1)

    # ── Step 1: Ingest from NSE (works from local/residential IP) ────
    try:
        from dividend_ingestion import DividendIngestionService
        svc = DividendIngestionService(conn, window_days=WINDOW_DAYS)
        svc.ensure_table()
        fetched = svc.run_full_ingestion()
        logger.info(f"Ingestion: {len(fetched)} new records upserted from NSE")
    except Exception as exc:
        logger.error(f"Ingestion failed: {exc}")
        conn.close()
        sys.exit(1)

    # ── Step 2: Read ALL upcoming dividends from DB ──────────────────
    # Scores existing records even if nothing new was fetched today.
    try:
        all_records = svc.get_upcoming_dividends()
        logger.info(f"Scoring: {len(all_records)} upcoming dividends from DB")
    except Exception as exc:
        logger.error(f"get_upcoming_dividends failed: {exc}")
        conn.close()
        sys.exit(1)

    if not all_records:
        logger.warning("No upcoming dividends in DB for next 14 days.")
        conn.close()
        sys.exit(0)

    # ── Step 3: Score locally (Kite + yfinance work here) ────────────
    try:
        from dividend_scoring import DividendScoringEngine
        engine = DividendScoringEngine(conn)
        scored = engine.score_all(all_records)
        engine.save_scores_to_db(scored)
        entry_signals = [s for s in scored if s.get("entry_signal")]
        logger.info(
            f"Scoring complete: {len(scored)} scored, "
            f"{len(entry_signals)} entry signals, "
            f"{sum(1 for s in scored if s.get('category') == 'Strong Buy')} Strong Buy"
        )
        for s in scored[:5]:
            logger.info(
                f"  {s['symbol']:15} score={s['dre_score']:3}  "
                f"{s['category']:12}  yield={s.get('yield_pct', 0):.1f}%  "
                f"{'SIGNAL' if s.get('entry_signal') else ''}"
            )
    except Exception as exc:
        logger.error(f"Scoring failed: {exc}")
        conn.close()
        sys.exit(1)

    conn.close()
    logger.info("DRE Local Cron — done. Scores written to Supabase.")


if __name__ == "__main__":
    main()
