"""
kite_client.py
==============
TradiqAI — Zerodha Kite Connect client

Provides:
  - OAuth 2.0 flow to obtain access_token
  - Real-time LTP via /quote/ltp endpoint
  - Historical OHLC candles for DMA calculation
  - Instrument token lookup (symbol → token)

Setup:
  1. Set KITE_API_KEY and KITE_API_SECRET in Railway environment
  2. Visit /api/kite/auth  →  log in with your Zerodha account
  3. /api/kite/callback stores the token in Supabase automatically
  4. Kite then powers DRE price/DMA scoring reliably from server IPs

The access_token expires every 24 hours. Re-visit /api/kite/auth each
morning (or automate with TOTP — see README).
"""

import csv
import hashlib
import io
import logging
import os
import time
from datetime import date, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

KITE_BASE_URL  = "https://api.kite.trade"
KITE_LOGIN_URL = "https://kite.trade/connect/login"
TOKEN_DB_KEY   = "kite_access_token"


class KiteClient:
    """Zerodha Kite Connect REST client."""

    # Class-level instrument cache (shared across instances)
    _instrument_cache: dict = {}   # "NSE:ITC" → instrument_token (int)
    _cache_loaded_at: float = 0    # epoch seconds

    def __init__(self):
        self.api_key      = os.environ.get("KITE_API_KEY", "")
        self.api_secret   = os.environ.get("KITE_API_SECRET", "")
        self.access_token = os.environ.get("KITE_ACCESS_TOKEN", "")
        self._session     = requests.Session()
        self._session.headers.update({"X-Kite-Version": "3"})

    # ── Authentication ────────────────────────────────────────────────

    @property
    def is_configured(self) -> bool:
        """True only when both api_key and access_token are set."""
        return bool(self.api_key and self.access_token)

    @property
    def login_url(self) -> str:
        return f"{KITE_LOGIN_URL}?api_key={self.api_key}&v=3"

    def generate_session(self, request_token: str) -> str:
        """
        Exchange a one-time request_token for a persistent access_token.
        Stores the token on self.access_token and returns it.
        """
        checksum = hashlib.sha256(
            f"{self.api_key}{request_token}{self.api_secret}".encode()
        ).hexdigest()

        resp = requests.post(
            f"{KITE_BASE_URL}/session/token",
            headers={"X-Kite-Version": "3"},
            data={
                "api_key":       self.api_key,
                "request_token": request_token,
                "checksum":      checksum,
            },
        )
        resp.raise_for_status()
        self.access_token = resp.json()["data"]["access_token"]
        logger.info("Kite: new session created successfully.")
        return self.access_token

    def _auth(self) -> dict:
        return {"Authorization": f"token {self.api_key}:{self.access_token}"}

    # ── Price Data ────────────────────────────────────────────────────

    def get_ltp(self, symbols: list) -> dict:
        """
        Last traded price for NSE symbols.

        Args:
            symbols: plain NSE symbols, e.g. ['ITC', 'TCS']

        Returns:
            {'NSE:ITC': {'last_price': 450.5}, 'NSE:TCS': {...}, ...}
        """
        instruments = [f"NSE:{s}" for s in symbols]
        resp = self._session.get(
            f"{KITE_BASE_URL}/quote/ltp",
            params={"i": instruments},
            headers=self._auth(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    def get_historical(
        self,
        instrument_token: int,
        from_date: str,   # YYYY-MM-DD
        to_date: str,     # YYYY-MM-DD
        interval: str = "day",
    ) -> list:
        """
        OHLCV candles.

        Returns:
            [[timestamp, open, high, low, close, volume], ...]
        """
        resp = self._session.get(
            f"{KITE_BASE_URL}/instruments/historical/{instrument_token}/{interval}",
            params={"from": from_date, "to": to_date},
            headers=self._auth(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("candles", [])

    # ── Instrument Lookup ─────────────────────────────────────────────

    def get_instrument_token(self, symbol: str, exchange: str = "NSE") -> Optional[int]:
        """Return the integer instrument_token for a symbol. Loads on demand."""
        self._ensure_instruments(exchange)
        return self._instrument_cache.get(f"{exchange}:{symbol}")

    def _ensure_instruments(self, exchange: str = "NSE"):
        """Refresh instrument list if older than 1 hour."""
        if time.time() - self._cache_loaded_at < 3600 and self._instrument_cache:
            return
        try:
            resp = self._session.get(
                f"{KITE_BASE_URL}/instruments/{exchange}",
                headers=self._auth(),
                timeout=30,
            )
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                key = f"{row.get('exchange', exchange)}:{row.get('tradingsymbol', '')}"
                try:
                    self._instrument_cache[key] = int(row["instrument_token"])
                except (KeyError, ValueError):
                    pass
            self._cache_loaded_at = time.time()
            logger.info(
                f"Kite: loaded {len(self._instrument_cache)} instruments for {exchange}"
            )
        except Exception as exc:
            logger.warning(f"Kite: failed to load instruments — {exc}")

    # ── Price + DMA bundle ────────────────────────────────────────────

    def fetch_price_data(self, symbol: str) -> Optional[dict]:
        """
        Fetch current price + 20/50/200-day SMAs for a symbol.
        Returns same shape as _fetch_price_data() in dividend_scoring.py,
        or None on failure.
        """
        if not self.is_configured:
            return None

        token = self.get_instrument_token(symbol)
        if not token:
            logger.debug(f"Kite: no instrument token for {symbol}")
            return None

        to_dt   = date.today()
        from_dt = to_dt - timedelta(days=300)   # ~200 trading days + buffer

        try:
            candles = self.get_historical(
                token,
                from_dt.strftime("%Y-%m-%d"),
                to_dt.strftime("%Y-%m-%d"),
            )
        except Exception as exc:
            logger.warning(f"Kite historical failed for {symbol}: {exc}")
            return None

        if not candles or len(candles) < 50:
            logger.debug(f"Kite: insufficient candles for {symbol} ({len(candles)})")
            return None

        closes = [c[4] for c in candles]   # index 4 = close
        price  = closes[-1]
        sma20  = sum(closes[-20:]) / 20
        sma50  = sum(closes[-50:]) / 50
        sma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None

        return {
            "price":        price,
            "sma20":        sma20,
            "sma50":        sma50,
            "sma200":       sma200,
            "above_20dma":  price > sma20,
            "above_50dma":  price > sma50,
            "above_200dma": (price > sma200) if sma200 else False,
            "5d_high":      max(c[4] for c in candles[-5:]),
        }


# ── Module-level singleton ────────────────────────────────────────────

_kite: Optional[KiteClient] = None


def get_kite() -> KiteClient:
    global _kite
    if _kite is None:
        _kite = KiteClient()
    return _kite


# ── Token persistence (Supabase) ──────────────────────────────────────

def load_token_from_db(db_conn) -> Optional[str]:
    """
    Load kite access_token from the app_settings table.
    Injects the token into the module-level KiteClient singleton.
    """
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM app_settings WHERE key = %s",
                (TOKEN_DB_KEY,),
            )
            row = cur.fetchone()
            if row:
                token = row[0]
                get_kite().access_token = token
                logger.info("Kite: access_token loaded from DB.")
                return token
    except Exception as exc:
        logger.debug(f"Kite: token not in DB ({exc})")
    return None


def save_token_to_db(db_conn, token: str):
    """Persist kite access_token to Supabase app_settings table."""
    try:
        with db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (TOKEN_DB_KEY, token),
            )
        db_conn.commit()
        logger.info("Kite: access_token saved to DB.")
    except Exception as exc:
        logger.warning(f"Kite: failed to save token to DB — {exc}")
