"""
dividend_backtest.py
====================
TradiqAI — Dividend Radar Engine
Full backtest engine implementing all 3 strategies from the DRE spec.

Strategies:
  S1 — Pre-Ex Run-Up     : buy N days before ex-date, exit 1 day before
  S2 — Dividend Capture  : buy N days before, hold through ex-date, exit +M days after
  S3 — Trend + Dividend  : S1 or S2 with trend/liquidity/yield filters

Outputs: per-trade log, summary stats, event study curves.

Usage:
    from dividend_backtest import DividendBacktester, BacktestConfig
    bt = DividendBacktester()
    results = bt.run(strategy="S1", entry_n=10, exit_offset=-1)
    bt.print_summary(results)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────

@dataclass
class BacktestConfig:
    strategy:          str   = "S1"     # S1 | S2 | S3
    entry_n:           int   = 10       # trading days before ex_date to enter
    exit_offset:       int   = -1       # S1: -1 day before. S2: +5, +10, +20

    # Cost model (basis points per side)
    brokerage_bps:     float = 15.0     # 0.15% per side (Zerodha/Groww approx)
    stt_bps:           float = 10.0     # STT delivery: 0.1% on sell side only
    slippage_bps:      float = 10.0     # market impact / slippage

    # Price execution
    use_open_next_day: bool  = True     # True = more realistic (next-day open)
    include_dividend:  bool  = False    # S2 only: add dividend cash to return
                                        # set True ONLY if using unadjusted prices

    # Filters (can toggle each)
    use_yield_filter:  bool  = True
    min_yield:         float = 2.0      # minimum yield % to consider
    use_trend_filter:  bool  = True     # price > SMA50
    use_volume_filter: bool  = True
    min_avg_value_cr:  float = 5.0      # min avg daily traded value in Crores
    skip_corp_overlap: bool  = True     # skip events with split/bonus in window

    # Portfolio mode
    portfolio_mode:    bool  = False
    initial_capital:   float = 50_000
    position_size_pct: float = 0.25     # 25% of capital per trade max
    max_open_pos:      int   = 2


# ─────────────────────────────────────────────
#  TRADING CALENDAR
# ─────────────────────────────────────────────

class NSETradingCalendar:
    """
    Simple NSE trading calendar.
    For production: load actual NSE holiday list from DB or file.
    """

    KNOWN_HOLIDAYS_2025_26 = {
        # 2025
        "2025-01-26","2025-02-19","2025-03-14","2025-04-14",
        "2025-04-18","2025-04-21","2025-04-30","2025-05-01",
        "2025-05-12","2025-08-15","2025-08-27","2025-10-02",
        "2025-10-02","2025-10-21","2025-10-22","2025-11-05",
        "2025-12-25",
        # 2026
        "2026-01-26","2026-03-02","2026-04-02","2026-04-14",
        "2026-04-03","2026-05-01","2026-08-15","2026-10-02",
    }

    def is_trading_day(self, dt: datetime) -> bool:
        if dt.weekday() >= 5:           # Saturday / Sunday
            return False
        if dt.strftime("%Y-%m-%d") in self.KNOWN_HOLIDAYS_2025_26:
            return False
        return True

    def offset(self, start_date: datetime, n_days: int) -> datetime:
        """
        Move start_date by n_days trading days.
        Negative n_days moves backward.
        """
        current = start_date
        step    = 1 if n_days >= 0 else -1
        remaining = abs(n_days)

        while remaining > 0:
            current += timedelta(days=step)
            if self.is_trading_day(current):
                remaining -= 1
        return current


CALENDAR = NSETradingCalendar()


# ─────────────────────────────────────────────
#  PRICE DATA LAYER
# ─────────────────────────────────────────────

def _load_price_data(symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """
    Load OHLCV price data for a symbol between start and end dates.
    Uses yfinance (add your own DB-based loader if you have prices_eod table).
    """
    try:
        import yfinance as yf
        ticker = f"{symbol}.NS"
        df = yf.download(ticker, start=start, end=end,
                         interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index)
        df = df[["Open","High","Low","Close","Volume"]].copy()
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as exc:
        logger.debug(f"Price load failed for {symbol}: {exc}")
        return None


def _get_price_on(df: pd.DataFrame, dt: datetime,
                  col: str = "close",
                  use_open_next_day: bool = True) -> Optional[float]:
    """
    Get execution price on or after a given date.
    If use_open_next_day: return open of the next available trading day.
    """
    if df is None or df.empty:
        return None

    if use_open_next_day:
        # Find first available date AFTER dt
        avail = df[df.index > pd.Timestamp(dt)]
        if avail.empty:
            return None
        return float(avail.iloc[0]["open"])
    else:
        # Use close on dt or nearest prior day
        avail = df[df.index <= pd.Timestamp(dt)]
        if avail.empty:
            return None
        return float(avail.iloc[-1][col])


def _compute_features(df: pd.DataFrame, as_of: datetime) -> dict:
    """
    Compute SMA20, SMA50, SMA200, avg volume as of a given date.
    """
    if df is None or df.empty:
        return {"sma50_ok": False, "sma200_ok": False, "vol_ok": False}

    sub = df[df.index <= pd.Timestamp(as_of)].copy()
    if sub.empty or len(sub) < 20:
        return {"sma50_ok": False, "sma200_ok": False, "vol_ok": False}

    price   = float(sub["close"].iloc[-1])
    sma50   = float(sub["close"].tail(50).mean()) if len(sub) >= 50 else None
    sma200  = float(sub["close"].tail(200).mean()) if len(sub) >= 200 else None
    avg_vol = float(sub["close"].tail(20).mean() * sub["volume"].tail(20).mean() / 1e7)  # Crores

    return {
        "price":     price,
        "sma50":     sma50,
        "sma200":    sma200,
        "avg_value_cr": avg_vol,
        "sma50_ok":  (price > sma50) if sma50 else False,
        "sma200_ok": (price > sma200) if sma200 else False,
        "vol_ok":    avg_vol >= 5.0,
    }


# ─────────────────────────────────────────────
#  COST MODEL
# ─────────────────────────────────────────────

def _apply_slippage(price: float, side: str, cfg: BacktestConfig) -> float:
    """
    Apply slippage to entry or exit price.
    side: 'buy' or 'sell'
    """
    slip = cfg.slippage_bps / 10_000
    return price * (1 + slip) if side == "buy" else price * (1 - slip)


def _total_costs(entry_price: float, exit_price: float, cfg: BacktestConfig) -> float:
    """
    Total round-trip cost as a fraction of capital.
    NSE delivery: brokerage both sides + STT on sell side.
    """
    brokerage = (entry_price + exit_price) * (cfg.brokerage_bps / 10_000)
    stt       = exit_price * (cfg.stt_bps / 10_000)
    return (brokerage + stt) / entry_price


# ─────────────────────────────────────────────
#  MAIN BACKTESTER
# ─────────────────────────────────────────────

@dataclass
class TradeRecord:
    symbol:          str
    ex_date:         str
    entry_date:      str
    exit_date:       str
    entry_price:     float
    exit_price:      float
    dividend_amount: float
    yield_pct:       float
    gross_return:    float
    net_return:      float
    costs:           float
    filters_passed:  dict  = field(default_factory=dict)
    notes:           str   = ""


class DividendBacktester:
    """
    Full backtest engine for all 3 DRE strategies.

    Example:
        from dividend_backtest import DividendBacktester, BacktestConfig

        bt   = DividendBacktester()
        cfg  = BacktestConfig(strategy="S1", entry_n=10, exit_offset=-1,
                              use_trend_filter=True, min_yield=2.0)
        df   = bt.load_events_from_csv("dividend_events.csv")   # or from DB
        res  = bt.run(events=df, cfg=cfg)
        bt.print_summary(res)
        bt.export_csv(res, "backtest_S1_results.csv")
    """

    def __init__(self, db_conn=None):
        self.db_conn  = db_conn
        self.calendar = CALENDAR

    def load_events_from_db(self, start_year: int = 2020) -> pd.DataFrame:
        """Load dividend events from TradiqAI's corporate_actions_dividends table."""
        if not self.db_conn:
            raise ValueError("No DB connection provided.")
        sql = """
            SELECT symbol, name, ex_date, dividend_amount, dividend_type, source
            FROM   corporate_actions_dividends
            WHERE  ex_date >= %s
              AND  dividend_amount > 0
              AND  symbol IS NOT NULL
            ORDER  BY ex_date ASC;
        """
        with self.db_conn.cursor() as cur:
            cur.execute(sql, (f"{start_year}-01-01",))
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)

    def load_events_from_csv(self, path: str) -> pd.DataFrame:
        """Load from CSV. Must have columns: symbol, ex_date, dividend_amount."""
        df = pd.read_csv(path, parse_dates=["ex_date"])
        df["ex_date"] = pd.to_datetime(df["ex_date"])
        return df

    def run(self, events: pd.DataFrame, cfg: BacktestConfig = None) -> list[TradeRecord]:
        """
        Main backtest loop.
        Returns list of TradeRecord.
        """
        if cfg is None:
            cfg = BacktestConfig()

        trades = []
        total  = len(events)
        logger.info(f"Backtest [{cfg.strategy}]: {total} events, "
                    f"entry N={cfg.entry_n}, exit_offset={cfg.exit_offset}")

        for i, row in events.iterrows():
            symbol      = str(row.get("symbol", "")).strip().upper()
            ex_date_raw = row.get("ex_date")
            div_amount  = float(row.get("dividend_amount", 0))

            if not symbol or pd.isna(ex_date_raw) or div_amount <= 0:
                continue

            ex_date = pd.Timestamp(ex_date_raw).to_pydatetime()

            # Calculate entry and exit dates
            t_entry = self.calendar.offset(ex_date, -cfg.entry_n)
            t_exit  = self.calendar.offset(ex_date, cfg.exit_offset)

            if t_entry >= ex_date and cfg.exit_offset < 0:
                continue  # sanity check

            # Determine data window needed
            data_start = (t_entry - timedelta(days=250)).strftime("%Y-%m-%d")
            data_end   = (t_exit  + timedelta(days=5)).strftime("%Y-%m-%d")

            df_prices = _load_price_data(symbol, data_start, data_end)
            if df_prices is None or df_prices.empty:
                logger.debug(f"  SKIP {symbol} — no price data")
                continue

            # Check required dates exist
            has_entry = not df_prices[df_prices.index.date == t_entry.date()].empty
            has_exit  = not df_prices[df_prices.index.date == t_exit.date()].empty
            if not has_entry and not has_exit:
                logger.debug(f"  SKIP {symbol} — missing entry or exit price")
                continue

            # Compute features for filters
            feats = _compute_features(df_prices, t_entry)

            # Filter: skip events with corporate action overlap (bonus/split)
            if cfg.skip_corp_overlap and self._has_corp_overlap(symbol, t_entry, t_exit):
                logger.debug(f"  SKIP {symbol} — corp action overlap")
                continue

            # Yield filter
            entry_close = feats.get("price", 0)
            yield_pct   = (div_amount / entry_close * 100) if entry_close else 0
            if cfg.use_yield_filter and yield_pct < cfg.min_yield:
                logger.debug(f"  SKIP {symbol} — yield {yield_pct:.1f}% < {cfg.min_yield}%")
                continue

            # Trend filter
            if cfg.use_trend_filter and not feats["sma50_ok"]:
                logger.debug(f"  SKIP {symbol} — price below SMA50")
                continue

            # Volume/liquidity filter
            if cfg.use_volume_filter and not feats["vol_ok"]:
                logger.debug(f"  SKIP {symbol} — low liquidity")
                continue

            # Get execution prices
            entry_px_raw = _get_price_on(df_prices, t_entry, use_open_next_day=cfg.use_open_next_day)
            exit_px_raw  = _get_price_on(df_prices, t_exit,  use_open_next_day=cfg.use_open_next_day)

            if not entry_px_raw or not exit_px_raw:
                continue

            # Apply slippage
            entry_px = _apply_slippage(entry_px_raw, "buy",  cfg)
            exit_px  = _apply_slippage(exit_px_raw,  "sell", cfg)

            # Return calculation
            gross = (exit_px - entry_px) / entry_px
            if cfg.strategy == "S2" and cfg.include_dividend:
                gross = (exit_px - entry_px + div_amount) / entry_px

            costs   = _total_costs(entry_px, exit_px, cfg)
            net     = gross - costs

            trades.append(TradeRecord(
                symbol          = symbol,
                ex_date         = ex_date.strftime("%Y-%m-%d"),
                entry_date      = t_entry.strftime("%Y-%m-%d"),
                exit_date       = t_exit.strftime("%Y-%m-%d"),
                entry_price     = round(entry_px, 2),
                exit_price      = round(exit_px, 2),
                dividend_amount = div_amount,
                yield_pct       = round(yield_pct, 2),
                gross_return    = round(gross * 100, 3),
                net_return      = round(net   * 100, 3),
                costs           = round(costs  * 100, 3),
                filters_passed  = {
                    "trend":    feats["sma50_ok"],
                    "liquidity":feats["vol_ok"],
                    "yield":    yield_pct >= cfg.min_yield,
                },
                notes = cfg.strategy,
            ))

        logger.info(f"Backtest complete: {len(trades)} valid trades from {total} events.")
        return trades

    def _has_corp_overlap(self, symbol: str, t_entry: datetime, t_exit: datetime) -> bool:
        """
        Check if there's a bonus / split in the trade window.
        Queries DB if available, else returns False (optimistic).
        """
        if not self.db_conn:
            return False
        try:
            sql = """
                SELECT 1
                FROM   corporate_actions_dividends
                WHERE  symbol = %s
                  AND  ex_date BETWEEN %s AND %s
                  AND  (purpose ILIKE '%%split%%' OR purpose ILIKE '%%bonus%%')
                LIMIT  1;
            """
            with self.db_conn.cursor() as cur:
                cur.execute(sql, (symbol,
                                  t_entry.strftime("%Y-%m-%d"),
                                  t_exit.strftime("%Y-%m-%d")))
                return cur.fetchone() is not None
        except Exception:
            return False

    # ─────────────────────────────────────────
    #  ANALYTICS
    # ─────────────────────────────────────────

    def summary_stats(self, trades: list[TradeRecord]) -> dict:
        """Compute summary statistics for a list of trades."""
        if not trades:
            return {"error": "No trades"}

        returns   = [t.net_return for t in trades]
        n         = len(returns)
        wins      = [r for r in returns if r > 0]
        losses    = [r for r in returns if r < 0]
        avg_r     = float(np.mean(returns))
        med_r     = float(np.median(returns))
        std_r     = float(np.std(returns))
        win_rate  = len(wins) / n * 100

        avg_win   = float(np.mean(wins))   if wins   else 0
        avg_loss  = float(np.mean(losses)) if losses else 0
        pf        = abs(sum(wins) / sum(losses)) if losses else float("inf")

        # Max drawdown (portfolio simulation, equal-weight)
        cum = np.cumprod([1 + r / 100 for r in returns])
        rolling_max = np.maximum.accumulate(cum)
        drawdown    = (cum - rolling_max) / rolling_max
        max_dd      = float(drawdown.min() * 100)

        # Top 10 trade concentration
        top10       = sum(sorted(wins, reverse=True)[:10])
        total_wins  = sum(wins) if wins else 1
        concentration = top10 / total_wins * 100 if wins else 0

        return {
            "n_trades":         n,
            "win_rate_pct":     round(win_rate, 1),
            "avg_net_return":   round(avg_r, 3),
            "median_return":    round(med_r, 3),
            "std_return":       round(std_r, 3),
            "avg_win":          round(avg_win, 3),
            "avg_loss":         round(avg_loss, 3),
            "profit_factor":    round(pf, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "top10_concentration_pct": round(concentration, 1),
            "total_gross_return": round(sum(t.gross_return for t in trades), 2),
            "total_net_return":   round(sum(returns), 2),
        }

    def event_study_df(self, trades: list[TradeRecord]) -> pd.DataFrame:
        """
        Return a DataFrame with cumulative average returns
        for event-study plotting (t=-N ... t=+M around ex-date).
        Loads fresh price data for each trade — use for research mode.
        """
        all_windows = []
        for t in trades:
            ex     = datetime.strptime(t.ex_date, "%Y-%m-%d")
            start  = (ex - timedelta(days=30)).strftime("%Y-%m-%d")
            end    = (ex + timedelta(days=30)).strftime("%Y-%m-%d")
            df_px  = _load_price_data(t.symbol, start, end)
            if df_px is None or df_px.empty:
                continue

            ex_row = df_px[df_px.index.date == ex.date()]
            if ex_row.empty:
                continue

            ex_close = float(ex_row["close"].iloc[0])
            # Normalise: relative return vs ex-date close
            df_px["rel_return"] = (df_px["close"] - ex_close) / ex_close * 100
            df_px["event_day"]  = (df_px.index - pd.Timestamp(ex)).dt.days
            df_px["symbol"]     = t.symbol

            window = df_px[
                (df_px["event_day"] >= -15) &
                (df_px["event_day"] <= 15)
            ][["event_day", "rel_return", "symbol"]]
            all_windows.append(window)

        if not all_windows:
            return pd.DataFrame()

        combined = pd.concat(all_windows)
        avg_curve = combined.groupby("event_day")["rel_return"].mean().reset_index()
        avg_curve.columns = ["day_relative_to_ex", "avg_return_pct"]
        return avg_curve

    def print_summary(self, trades: list[TradeRecord]):
        """Pretty-print backtest summary to console."""
        stats = self.summary_stats(trades)
        print("\n" + "═" * 55)
        print(f"  DRE BACKTEST SUMMARY")
        print("═" * 55)
        for k, v in stats.items():
            print(f"  {k:<35} {v:>10}")
        print("═" * 55)
        print(f"\n  Top 5 Trades by Net Return:")
        for t in sorted(trades, key=lambda x: x.net_return, reverse=True)[:5]:
            print(f"    {t.symbol:12} ex={t.ex_date}  net={t.net_return:+.2f}%  yield={t.yield_pct:.1f}%")
        print(f"\n  Worst 5 Trades:")
        for t in sorted(trades, key=lambda x: x.net_return)[:5]:
            print(f"    {t.symbol:12} ex={t.ex_date}  net={t.net_return:+.2f}%  yield={t.yield_pct:.1f}%")
        print()

    def export_csv(self, trades: list[TradeRecord], path: str):
        """Export trades to CSV for further analysis."""
        import csv
        import dataclasses
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "symbol","ex_date","entry_date","exit_date",
                "entry_price","exit_price","dividend_amount","yield_pct",
                "gross_return","net_return","costs","notes"
            ])
            writer.writeheader()
            for t in trades:
                writer.writerow({
                    k: getattr(t, k)
                    for k in ["symbol","ex_date","entry_date","exit_date",
                              "entry_price","exit_price","dividend_amount","yield_pct",
                              "gross_return","net_return","costs","notes"]
                })
        logger.info(f"Exported {len(trades)} trades to {path}")

    def robustness_check(
        self,
        events: pd.DataFrame,
        entry_ns: list[int]     = [5, 10, 15],
        exit_offsets: list[int] = [-1, 5, 10, 20],
    ) -> pd.DataFrame:
        """
        Run backtest across all combinations of N and exit_offset.
        Returns a DataFrame of summary stats per combo.
        """
        rows = []
        for n in entry_ns:
            for offset in exit_offsets:
                strat = "S1" if offset < 0 else "S2"
                cfg   = BacktestConfig(
                    strategy    = strat,
                    entry_n     = n,
                    exit_offset = offset,
                )
                trades = self.run(events, cfg)
                if not trades:
                    continue
                s = self.summary_stats(trades)
                s["entry_n"]     = n
                s["exit_offset"] = offset
                s["strategy"]    = strat
                rows.append(s)

        return pd.DataFrame(rows).sort_values("profit_factor", ascending=False)


# ─────────────────────────────────────────────
#  STANDALONE TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

    # Sample events (replace with bt.load_events_from_db() in production)
    sample_events = pd.DataFrame([
        {"symbol": "ITC",       "ex_date": "2025-07-10", "dividend_amount": 6.0},
        {"symbol": "COALINDIA", "ex_date": "2025-08-05", "dividend_amount": 14.5},
        {"symbol": "POWERGRID", "ex_date": "2025-09-12", "dividend_amount": 7.5},
        {"symbol": "NESTLEIND", "ex_date": "2025-06-20", "dividend_amount": 75.0},
    ])

    bt  = DividendBacktester()
    cfg = BacktestConfig(
        strategy           = "S1",
        entry_n            = 10,
        exit_offset        = -1,
        use_trend_filter   = True,
        use_yield_filter   = True,
        min_yield          = 2.0,
        use_volume_filter  = False,   # skip for small test
    )

    trades = bt.run(events=sample_events, cfg=cfg)
    bt.print_summary(trades)

    print("\n📊 Robustness Check (all N × offset combinations):")
    rob = bt.robustness_check(sample_events)
    print(rob[["strategy","entry_n","exit_offset","n_trades","win_rate_pct",
               "avg_net_return","profit_factor"]].to_string(index=False))
