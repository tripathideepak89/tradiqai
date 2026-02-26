"""
dividend_ingestion.py
=====================
TradiqAI — Dividend Radar Engine
Data ingestion layer: NSE (primary) → BSE (fallback) → MoneyControl (validation)

Drop this file in your TradiqAI root directory.
Requires: requests, beautifulsoup4, psycopg2 (already in your requirements.txt)

Usage:
    from dividend_ingestion import DividendIngestionService
    svc = DividendIngestionService(db_conn)
    svc.run_full_ingestion()
"""

import re
import time
import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  UNIFIED SCHEMA
#  Every source normalises into this dict shape
# ─────────────────────────────────────────────
SCHEMA_KEYS = [
    "symbol",           # NSE ticker  (str)
    "bse_code",         # BSE numeric code  (str | None)
    "name",             # Full company name  (str)
    "series",           # EQ / BE / N (NSE series)
    "exchange",         # NSE | BSE
    "purpose",          # Raw purpose string from exchange
    "dividend_type",    # Final | Interim | Special
    "dividend_amount",  # Parsed ₹ amount  (float)
    "face_value",       # Face value  (float | None)
    "ex_date",          # YYYY-MM-DD  (str)
    "record_date",      # YYYY-MM-DD  (str | None)
    "bc_start_date",    # Book closure start  (str | None)
    "bc_end_date",      # Book closure end  (str | None)
    "nd_start_date",    # No-delivery start (BSE)  (str | None)
    "nd_end_date",      # No-delivery end (BSE)    (str | None)
    "payment_date",     # Actual payment date (BSE) (str | None)
    "announcement_date",# When announced  (str | None)
    "source",           # NSE | BSE | MC
    "ingested_at",      # UTC timestamp  (str)
]


# ─────────────────────────────────────────────
#  DATE HELPERS
# ─────────────────────────────────────────────

def _parse_date(raw: str) -> Optional[str]:
    """Convert any common date format → YYYY-MM-DD. Returns None if unparseable."""
    if not raw or str(raw).strip() in ("-", "N/A", "NA", ""):
        return None
    raw = str(raw).strip()

    # DD-MM-YYYY  (NSE)
    m = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    # DD/MM/YYYY  (BSE, MoneyControl)
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    # Already YYYY-MM-DD
    m = re.match(r"^\d{4}-\d{2}-\d{2}$", raw)
    if m:
        return raw

    # DD-Mon-YYYY  e.g. 12-Mar-2026
    try:
        return datetime.strptime(raw, "%d-%b-%Y").strftime("%Y-%m-%d")
    except ValueError:
        pass

    logger.warning(f"Could not parse date: {raw!r}")
    return None


def _parse_dividend_amount(purpose: str) -> float:
    """
    Extract ₹ amount from purpose strings like:
      "Dividend - Rs 6.50 Per Share"
      "INTERIM DIV RS.3/-"
      "Special Dividend Rs 14.5 per share"
      "Dividend @ 150%"    ← percentage-based (face value needed separately)
    Returns 0.0 if not found.
    """
    if not purpose:
        return 0.0
    # Rs / INR amount
    m = re.search(r"(?:rs\.?|inr)\s*(\d+(?:\.\d+)?)", purpose, re.IGNORECASE)
    if m:
        return float(m.group(1))
    # Plain number before "per share"
    m = re.search(r"(\d+(?:\.\d+)?)\s*per\s*share", purpose, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return 0.0


def _parse_dividend_type(purpose: str) -> str:
    p = purpose.upper() if purpose else ""
    if "SPECIAL" in p:
        return "Special"
    if "INTERIM" in p:
        return "Interim"
    if "FINAL" in p:
        return "Final"
    if "ANNUAL" in p:
        return "Final"
    return "Dividend"


def _now_utc() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────
#  SOURCE 1: NSE  (PRIMARY)
# ─────────────────────────────────────────────

NSE_HOME        = "https://www.nseindia.com"
NSE_ACTIONS_URL = "https://www.nseindia.com/api/corporates-corporateActions"
NSE_HEADERS     = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.nseindia.com/companies-listing/corporate-filings-actions",
    "X-Requested-With": "XMLHttpRequest",
}


class NSEFetcher:
    """
    NSE requires a live browser session cookie before the API responds.
    Strategy: init session → hit homepage → hit page → call API.
    Cache session for up to 30 minutes.
    """

    def __init__(self):
        self.session      = None
        self.session_time = None
        self.SESSION_TTL  = 1800  # seconds

    def _init_session(self):
        if (self.session_time and
                (time.time() - self.session_time) < self.SESSION_TTL):
            return  # reuse

        logger.info("NSE: initialising new session…")
        s = requests.Session()
        s.headers.update(NSE_HEADERS)

        try:
            # Step 1 — hit homepage to get base cookies
            r = s.get(NSE_HOME, timeout=15)
            r.raise_for_status()
            time.sleep(1.5)

            # Step 2 — hit the corporate actions page (triggers more cookies)
            r = s.get(
                f"{NSE_HOME}/companies-listing/corporate-filings-actions",
                timeout=15
            )
            r.raise_for_status()
            time.sleep(1.0)

            self.session      = s
            self.session_time = time.time()
            logger.info("NSE: session initialised successfully.")

        except Exception as exc:
            logger.error(f"NSE: session init failed — {exc}")
            self.session = None

    def fetch(self, from_date: str, to_date: str) -> list[dict]:
        """
        Fetch dividend announcements from NSE.

        Args:
            from_date: DD-MM-YYYY
            to_date:   DD-MM-YYYY

        Returns:
            List of normalised dicts (unified schema).
        """
        self._init_session()
        if not self.session:
            logger.warning("NSE: no session, skipping.")
            return []

        params = {
            "index":     "equities",
            "from_date": from_date,
            "to_date":   to_date,
        }

        try:
            resp = self.session.get(
                NSE_ACTIONS_URL,
                params=params,
                timeout=20
            )
            resp.raise_for_status()
            raw_list = resp.json()

            # NSE returns a list of dicts; filter dividends
            results = []
            for r in raw_list:
                purpose = str(r.get("subject", "")).upper()
                if "DIVIDEND" not in purpose and "DIV" not in purpose:
                    continue
                results.append(self._normalise(r))

            logger.info(f"NSE: fetched {len(results)} dividend records.")
            return results

        except Exception as exc:
            logger.error(f"NSE fetch error: {exc}")
            self.session = None  # force re-init next time
            return []

    @staticmethod
    def _normalise(r: dict) -> dict:
        purpose = r.get("subject", "")
        return {
            "symbol":            r.get("symbol", ""),
            "bse_code":          None,
            "name":              r.get("companyName", r.get("symbol", "")),
            "series":            r.get("series", "EQ"),
            "exchange":          "NSE",
            "purpose":           purpose,
            "dividend_type":     _parse_dividend_type(purpose),
            "dividend_amount":   _parse_dividend_amount(purpose),
            "face_value":        _safe_float(r.get("faceVal")),
            "ex_date":           _parse_date(r.get("exDate", "")),
            "record_date":       _parse_date(r.get("recDate", "")),
            "bc_start_date":     _parse_date(r.get("bcStartDate", "")),
            "bc_end_date":       _parse_date(r.get("bcEndDate", "")),
            "nd_start_date":     None,
            "nd_end_date":       None,
            "payment_date":      None,
            "announcement_date": _parse_date(r.get("ndStartDate", "")),
            "source":            "NSE",
            "ingested_at":       _now_utc(),
        }


# ─────────────────────────────────────────────
#  SOURCE 2: BSE  (FALLBACK / ENRICHMENT)
# ─────────────────────────────────────────────

BSE_API_URL = "https://api.bseindia.com/BseIndiaAPI/api/DefaultData/w"
BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer":    "https://www.bseindia.com",
    "Origin":     "https://www.bseindia.com",
}


class BSEFetcher:
    """
    BSE has a relatively open JSON API — simpler than NSE.
    CAType=4 → Dividend events.
    """

    def fetch(self, from_date: str, to_date: str) -> list[dict]:
        """
        Args:
            from_date: DD/MM/YYYY
            to_date:   DD/MM/YYYY

        Returns:
            List of normalised dicts.
        """
        params = {
            "Grp":        "CA",
            "CAType":     "4",       # 4 = Dividend
            "scripcode":  "",        # empty = all
            "strdate":    from_date,
            "enddate":    to_date,
            "ddlcategorys": "E",     # E = Equity
        }
        try:
            resp = requests.get(
                BSE_API_URL,
                params=params,
                headers=BSE_HEADERS,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()

            # BSE returns {"Table": [...]}  or  [...]
            rows = data.get("Table", data) if isinstance(data, dict) else data
            results = [self._normalise(r) for r in rows if isinstance(r, dict)]
            logger.info(f"BSE: fetched {len(results)} dividend records.")
            return results

        except Exception as exc:
            logger.error(f"BSE fetch error: {exc}")
            return []

    @staticmethod
    def _normalise(r: dict) -> dict:
        purpose = r.get("PURPOSE", r.get("purpose", ""))
        return {
            "symbol":            None,  # BSE doesn't return NSE ticker natively
            "bse_code":          str(r.get("SCRIP_CD", r.get("scripCd", ""))),
            "name":              r.get("SCRIP_NAME", r.get("scripName", "")),
            "series":            None,
            "exchange":          "BSE",
            "purpose":           purpose,
            "dividend_type":     _parse_dividend_type(purpose),
            "dividend_amount":   _parse_dividend_amount(purpose),
            "face_value":        None,
            "ex_date":           _parse_date(r.get("EX_DATE", r.get("exDate", ""))),
            "record_date":       _parse_date(r.get("REC_DATE", r.get("recDate", ""))),
            "bc_start_date":     _parse_date(r.get("BC_START_DT", "")),
            "bc_end_date":       _parse_date(r.get("BC_END_DT", "")),
            "nd_start_date":     _parse_date(r.get("ND_START_DT", "")),
            "nd_end_date":       _parse_date(r.get("ND_END_DT", "")),
            "payment_date":      _parse_date(r.get("PAYMENT_DATE", r.get("paymentDate", ""))),
            "announcement_date": None,
            "source":            "BSE",
            "ingested_at":       _now_utc(),
        }


# ─────────────────────────────────────────────
#  SOURCE 3: MONEYCONTROL  (VALIDATION ONLY)
# ─────────────────────────────────────────────

MC_URL = "https://www.moneycontrol.com/markets/corporate-action/dividends_declared/"
MC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Referer": "https://www.moneycontrol.com/",
}


class MoneyControlFetcher:
    """
    MoneyControl — scrape-based, used ONLY for cross-validation.
    Do not use as primary source. Rate-limit carefully.
    """

    def fetch(self) -> list[dict]:
        try:
            resp = requests.get(MC_URL, headers=MC_HEADERS, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")

            # MC uses various table class names; try the most common ones
            table = (
                soup.find("table", {"class": "mctable1"})
                or soup.find("table", {"id": "div_declared_table"})
                or soup.find("div", {"class": "bsr_table"})
            )
            if not table:
                logger.warning("MoneyControl: could not find dividend table.")
                return []

            rows = table.find_all("tr")[1:]  # skip header
            results = []
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cols) >= 4:
                    results.append(self._normalise(cols))

            logger.info(f"MoneyControl: scraped {len(results)} records.")
            return results

        except Exception as exc:
            logger.error(f"MoneyControl scrape error: {exc}")
            return []

    @staticmethod
    def _normalise(cols: list) -> dict:
        # Typical MC columns: Company | Amount | Type | Ex-Date | Record Date
        purpose = f"Dividend {cols[2] if len(cols) > 2 else ''} Rs {cols[1] if len(cols) > 1 else '0'} Per Share"
        return {
            "symbol":            None,
            "bse_code":          None,
            "name":              cols[0] if cols else "",
            "series":            None,
            "exchange":          "MC",
            "purpose":           purpose,
            "dividend_type":     _parse_dividend_type(cols[2] if len(cols) > 2 else ""),
            "dividend_amount":   _safe_float(cols[1]) if len(cols) > 1 else 0.0,
            "face_value":        None,
            "ex_date":           _parse_date(cols[3]) if len(cols) > 3 else None,
            "record_date":       _parse_date(cols[4]) if len(cols) > 4 else None,
            "bc_start_date":     None,
            "bc_end_date":       None,
            "nd_start_date":     None,
            "nd_end_date":       None,
            "payment_date":      None,
            "announcement_date": None,
            "source":            "MC",
            "ingested_at":       _now_utc(),
        }


# ─────────────────────────────────────────────
#  MERGE + DEDUPLICATION
# ─────────────────────────────────────────────

def merge_and_deduplicate(
    nse_records: list[dict],
    bse_records: list[dict],
    mc_records: list[dict],
) -> list[dict]:
    """
    Priority: NSE > BSE > MC
    Dedup key: (symbol_or_name_normalised, ex_date, dividend_amount)
    If same event from NSE + BSE: keep NSE record, but enrich with
    BSE-only fields (payment_date, nd_start_date, nd_end_date).
    """
    seen: dict[str, dict] = {}

    def _key(r: dict) -> str:
        name_part = (
            (r.get("symbol") or r.get("name") or "")
            .upper()
            .replace(" LTD", "")
            .replace(" LIMITED", "")
            .replace(" ", "")
        )
        ex    = r.get("ex_date") or ""
        amt   = str(round(r.get("dividend_amount") or 0, 2))
        return f"{name_part}|{ex}|{amt}"

    def _enrich(master: dict, secondary: dict) -> dict:
        """Fill None fields in master from secondary."""
        for k in ("payment_date", "nd_start_date", "nd_end_date",
                  "record_date", "bse_code"):
            if not master.get(k) and secondary.get(k):
                master[k] = secondary[k]
        return master

    # Process in priority order
    for records in (nse_records, bse_records, mc_records):
        for rec in records:
            if not rec.get("ex_date"):
                continue  # skip records without ex-date
            key = _key(rec)
            if key in seen:
                # Enrich existing record with any new fields
                seen[key] = _enrich(seen[key], rec)
            else:
                seen[key] = rec

    merged = list(seen.values())
    logger.info(f"Merge: {len(nse_records)} NSE + {len(bse_records)} BSE + "
                f"{len(mc_records)} MC → {len(merged)} unique records after dedup.")
    return merged


# ─────────────────────────────────────────────
#  DATABASE UPSERT  (PostgreSQL / Supabase)
# ─────────────────────────────────────────────

UPSERT_SQL = """
INSERT INTO corporate_actions_dividends (
    symbol, bse_code, name, series, exchange,
    purpose, dividend_type, dividend_amount, face_value,
    ex_date, record_date, bc_start_date, bc_end_date,
    nd_start_date, nd_end_date, payment_date, announcement_date,
    source, ingested_at
)
VALUES (
    %(symbol)s, %(bse_code)s, %(name)s, %(series)s, %(exchange)s,
    %(purpose)s, %(dividend_type)s, %(dividend_amount)s, %(face_value)s,
    %(ex_date)s, %(record_date)s, %(bc_start_date)s, %(bc_end_date)s,
    %(nd_start_date)s, %(nd_end_date)s, %(payment_date)s, %(announcement_date)s,
    %(source)s, %(ingested_at)s
)
ON CONFLICT (symbol_dedup_key, ex_date, dividend_amount_rounded)
DO UPDATE SET
    payment_date      = COALESCE(EXCLUDED.payment_date,      corporate_actions_dividends.payment_date),
    record_date       = COALESCE(EXCLUDED.record_date,       corporate_actions_dividends.record_date),
    nd_start_date     = COALESCE(EXCLUDED.nd_start_date,     corporate_actions_dividends.nd_start_date),
    nd_end_date       = COALESCE(EXCLUDED.nd_end_date,       corporate_actions_dividends.nd_end_date),
    ingested_at       = EXCLUDED.ingested_at,
    source            = CASE WHEN EXCLUDED.source = 'NSE' THEN 'NSE'
                             ELSE corporate_actions_dividends.source END;
"""

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS corporate_actions_dividends (
    id                    SERIAL PRIMARY KEY,
    symbol                VARCHAR(20),
    bse_code              VARCHAR(10),
    name                  TEXT NOT NULL,
    series                VARCHAR(5),
    exchange              VARCHAR(5),
    purpose               TEXT,
    dividend_type         VARCHAR(20),
    dividend_amount       NUMERIC(10,2),
    face_value            NUMERIC(10,2),
    ex_date               DATE NOT NULL,
    record_date           DATE,
    bc_start_date         DATE,
    bc_end_date           DATE,
    nd_start_date         DATE,
    nd_end_date           DATE,
    payment_date          DATE,
    announcement_date     DATE,
    source                VARCHAR(5),
    ingested_at           TIMESTAMPTZ DEFAULT NOW(),

    -- Computed columns for deduplication
    symbol_dedup_key      TEXT GENERATED ALWAYS AS (
        UPPER(REGEXP_REPLACE(COALESCE(symbol, name), '[^A-Z0-9]', '', 'g'))
    ) STORED,
    dividend_amount_rounded NUMERIC(8,1) GENERATED ALWAYS AS (
        ROUND(COALESCE(dividend_amount, 0), 1)
    ) STORED,

    UNIQUE (symbol_dedup_key, ex_date, dividend_amount_rounded)
);

CREATE INDEX IF NOT EXISTS idx_div_ex_date   ON corporate_actions_dividends(ex_date);
CREATE INDEX IF NOT EXISTS idx_div_symbol    ON corporate_actions_dividends(symbol);
CREATE INDEX IF NOT EXISTS idx_div_source    ON corporate_actions_dividends(source);
"""


# ─────────────────────────────────────────────
#  MAIN SERVICE
# ─────────────────────────────────────────────

class DividendIngestionService:
    """
    Main entry point. Wires together NSE → BSE → MC → dedup → DB.

    Usage:
        import psycopg2
        from dividend_ingestion import DividendIngestionService

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        svc  = DividendIngestionService(conn)
        svc.ensure_table()
        svc.run_full_ingestion()
    """

    def __init__(self, db_conn, window_days: int = 14):
        self.conn        = db_conn
        self.window_days = window_days
        self.nse         = NSEFetcher()
        self.bse         = BSEFetcher()
        self.mc          = MoneyControlFetcher()

    def ensure_table(self):
        """Create table and indexes if they don't exist."""
        with self.conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
        self.conn.commit()
        logger.info("DB: corporate_actions_dividends table ready.")

    def run_full_ingestion(self) -> list[dict]:
        """
        Full pipeline:
          1. Calculate date range (today → today + window_days)
          2. Fetch from NSE, BSE, MC
          3. Deduplicate
          4. Filter: only dividends with ex_date in window
          5. Upsert to DB
          6. Return normalised records for downstream scoring

        Called by the 6:30 AM scheduler.
        """
        today   = datetime.now()
        end     = today + timedelta(days=self.window_days)

        # NSE format: DD-MM-YYYY
        nse_from = today.strftime("%d-%m-%Y")
        nse_to   = end.strftime("%d-%m-%Y")

        # BSE/MC format: DD/MM/YYYY
        bse_from = today.strftime("%d/%m/%Y")
        bse_to   = end.strftime("%d/%m/%Y")

        logger.info(f"DRE Ingestion: {nse_from} → {nse_to}")

        nse_data = self.nse.fetch(nse_from, nse_to)
        bse_data = self.bse.fetch(bse_from, bse_to)
        mc_data  = self.mc.fetch()   # MC doesn't support date params; filter post-fetch

        # Filter MC to window
        today_str = today.strftime("%Y-%m-%d")
        end_str   = end.strftime("%Y-%m-%d")
        mc_data = [
            r for r in mc_data
            if r.get("ex_date") and today_str <= r["ex_date"] <= end_str
        ]

        merged = merge_and_deduplicate(nse_data, bse_data, mc_data)

        # Filter: ex_date must be valid and within window
        merged = [
            r for r in merged
            if r.get("ex_date") and today_str <= r["ex_date"] <= end_str
        ]

        self._upsert_all(merged)
        return merged

    def _upsert_all(self, records: list[dict]):
        if not records:
            logger.info("DB: nothing to upsert.")
            return
        with self.conn.cursor() as cur:
            for rec in records:
                try:
                    cur.execute(UPSERT_SQL, rec)
                except Exception as exc:
                    logger.warning(f"Upsert skipped for {rec.get('symbol')} / {rec.get('name')}: {exc}")
                    self.conn.rollback()
                    continue
        self.conn.commit()
        logger.info(f"DB: upserted {len(records)} dividend records.")

    def get_upcoming_dividends(self) -> list[dict]:
        """
        Read upcoming dividends from DB for the scoring engine.
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        end_str   = (datetime.now() + timedelta(days=self.window_days)).strftime("%Y-%m-%d")
        sql = """
            SELECT *
            FROM   corporate_actions_dividends
            WHERE  ex_date BETWEEN %s AND %s
            ORDER  BY ex_date ASC;
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (today_str, end_str))
            cols    = [desc[0] for desc in cur.description]
            rows    = cur.fetchall()
            return [dict(zip(cols, row)) for row in rows]


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _safe_float(val) -> Optional[float]:
    try:
        return float(val) if val not in (None, "", "-") else None
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────
#  STANDALONE TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

    # Quick test without DB
    nse     = NSEFetcher()
    results = nse.fetch("26-02-2026", "12-03-2026")
    print(f"\nNSE fetched: {len(results)} records")
    for r in results[:3]:
        print(f"  {r['symbol']:15} ex={r['ex_date']}  ₹{r['dividend_amount']}  ({r['dividend_type']})")
