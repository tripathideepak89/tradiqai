"""Trading Status Monitor - Logs trading summary every 30 minutes"""
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
from database import SessionLocal
from models import Trade
from utils import now_ist

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

monitor_log = log_dir / "trading_monitor.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(monitor_log),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def parse_log_signals(log_file: Path) -> Dict[str, List[Dict]]:
    """Parse recent signals from trading log"""
    signals = {"approved": [], "rejected": []}
    
    if not log_file.exists():
        return signals
    
    # Read last 1000 lines (roughly last 30 mins of activity)
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-1000:]
        
        for i, line in enumerate(lines):
            if "Executing signal for" in line:
                # Extract symbol and direction
                parts = line.split("Executing signal for")[1].strip().split(":")
                if len(parts) >= 2:
                    symbol = parts[0].strip()
                    direction = parts[1].strip()
                    
                    # Look for the next line with risk check result
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        if "approved=True" in next_line:
                            signals["approved"].append({
                                "symbol": symbol,
                                "direction": direction,
                                "time": line.split(" - ")[0]
                            })
                        elif "approved=False" in next_line:
                            reason_parts = next_line.split("reason=")
                            reason = reason_parts[1] if len(reason_parts) > 1 else "Unknown"
                            signals["rejected"].append({
                                "symbol": symbol,
                                "direction": direction,
                                "reason": reason.strip(),
                                "time": line.split(" - ")[0]
                            })
    except Exception as e:
        logger.error(f"Error parsing log: {e}")
    
    return signals


def get_trading_summary() -> str:
    """Generate trading summary for last 30 minutes"""
    now = now_ist()
    session = SessionLocal()
    
    try:
        # Get today's trades
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        trades = session.query(Trade).filter(
            Trade.entry_timestamp >= today_start
        ).all()
        
        # Calculate P&L
        total_pnl = sum(t.net_pnl or 0 for t in trades)
        open_positions = [t for t in trades if t.status == 'open']
        closed_trades = [t for t in trades if t.status == 'closed']
        
        # Parse recent signals from log
        today_log = Path(f"logs/trading_{now.strftime('%Y-%m-%d')}.log")
        signals = parse_log_signals(today_log)
        
        # Count unique signals in last 30 mins
        cutoff_time = now - timedelta(minutes=30)
        recent_approved = [s for s in signals["approved"] 
                          if datetime.strptime(s["time"], "%Y-%m-%d %H:%M:%S,%f") > cutoff_time]
        recent_rejected = [s for s in signals["rejected"] 
                          if datetime.strptime(s["time"], "%Y-%m-%d %H:%M:%S,%f") > cutoff_time]
        
        # Build summary
        summary = []
        summary.append("=" * 80)
        summary.append(f"TRADING STATUS REPORT - {now.strftime('%Y-%m-%d %H:%M:%S IST')}")
        summary.append("=" * 80)
        summary.append("")
        
        # Overall stats
        summary.append("[PERFORMANCE] TODAY'S PERFORMANCE:")
        summary.append(f"   Total Trades: {len(trades)}")
        summary.append(f"   Open Positions: {len(open_positions)}")
        summary.append(f"   Closed Trades: {len(closed_trades)}")
        summary.append(f"   P&L: Rs{total_pnl:,.2f}")
        summary.append("")
        
        # Open positions
        if open_positions:
            summary.append("[POSITIONS] OPEN POSITIONS:")
            for trade in open_positions:
                summary.append(f"   {trade.symbol} | {trade.direction} | "
                             f"Entry: Rs{trade.entry_price} x {trade.quantity} | "
                             f"Time: {trade.entry_timestamp.strftime('%H:%M:%S')}")
        else:
            summary.append("[POSITIONS] OPEN POSITIONS: None")
        summary.append("")
        
        # Last 30 mins activity
        summary.append(f"[ACTIVITY] LAST 30 MINUTES:")
        summary.append(f"   Approved Signals: {len(recent_approved)}")
        if recent_approved:
            for sig in recent_approved[-5:]:  # Last 5
                summary.append(f"      [OK] {sig['symbol']} ({sig['direction']}) at {sig['time'].split()[1]}")
        
        summary.append(f"   Rejected Signals: {len(recent_rejected)}")
        if recent_rejected:
            rejection_counts = {}
            for sig in recent_rejected:
                rejection_counts[sig['symbol']] = rejection_counts.get(sig['symbol'], 0) + 1
            
            for symbol, count in list(rejection_counts.items())[:5]:  # Top 5
                summary.append(f"      [X] {symbol} ({count}x)")
        
        summary.append("")
        summary.append("=" * 80)
        summary.append("")
        
        return "\n".join(summary)
        
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return f"Error generating summary: {e}"
    finally:
        session.close()


def main():
    """Main monitoring loop"""
    logger.info(">> Trading Monitor Started")
    logger.info(f"Writing updates to: {monitor_log}")
    logger.info("Update interval: 30 minutes")
    logger.info("")
    
    # Immediate first report
    summary = get_trading_summary()
    logger.info(summary)
    
    # Then run every 30 minutes
    while True:
        try:
            time.sleep(30 * 60)  # 30 minutes
            summary = get_trading_summary()
            logger.info(summary)
            
        except KeyboardInterrupt:
            logger.info("\n[X] Monitor stopped by user")
            break
        except Exception as e:
            logger.error(f"[!] Monitor error: {e}")
            time.sleep(60)  # Wait 1 minute before retry


if __name__ == "__main__":
    main()
