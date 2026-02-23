"""Live Trading System Monitor - Real-time dashboard"""
import os
import time
import asyncio
from datetime import datetime
from typing import List, Dict
from sqlalchemy import desc

from database import SessionLocal
from models import Trade, DailyMetrics, TradeStatus
from brokers.factory import BrokerFactory
from config import settings
from utils.timezone import now_ist, format_ist, today_ist, IST

# ANSI color codes for terminal
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Print dashboard header"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*80}")
    print(f"  AUTOTRADE AI - LIVE MONITORING DASHBOARD")
    print(f"  {format_ist(now_ist())}")
    print(f"{'='*80}{Colors.END}\n")


def print_system_status(broker):
    """Print system health status"""
    print(f"{Colors.BOLD}[SYSTEM STATUS]{Colors.END}")
    print(f"  Broker: {Colors.GREEN}{settings.broker.upper()}{Colors.END}")
    print(f"  Mode: {Colors.YELLOW}{'PAPER TRADING' if settings.paper_trading else 'LIVE TRADING'}{Colors.END}")
    print(f"  Capital: {Colors.CYAN}₹{settings.initial_capital:,.2f}{Colors.END}")
    print()


def print_account_info(margins: Dict):
    """Print account information"""
    print(f"{Colors.BOLD}[ACCOUNT MARGINS]{Colors.END}")
    available = margins.get('available_margin', 0)
    used = margins.get('used_margin', 0)
    total = available + used
    
    print(f"  Total Margin: {Colors.WHITE}₹{total:,.2f}{Colors.END}")
    print(f"  Available: {Colors.GREEN}₹{available:,.2f}{Colors.END}")
    print(f"  Used: {Colors.YELLOW}₹{used:,.2f}{Colors.END}")
    print()


def print_daily_metrics(db):
    """Print today's trading metrics"""
    today = today_ist().date()
    metrics = db.query(DailyMetrics).filter(
        DailyMetrics.date == today
    ).first()
    
    print(f"{Colors.BOLD}[TODAY'S PERFORMANCE]{Colors.END}")
    
    if metrics:
        pnl_color = Colors.GREEN if metrics.total_pnl >= 0 else Colors.RED
        print(f"  P&L: {pnl_color}₹{metrics.total_pnl:,.2f}{Colors.END}")
        print(f"  Trades: {Colors.WHITE}{metrics.trades_count}{Colors.END} "
              f"(Win: {Colors.GREEN}{metrics.winning_trades}{Colors.END}, "
              f"Loss: {Colors.RED}{metrics.losing_trades}{Colors.END})")
        
        if metrics.trades_count > 0:
            win_rate = (metrics.winning_trades / metrics.trades_count) * 100
            print(f"  Win Rate: {Colors.CYAN}{win_rate:.1f}%{Colors.END}")
        
        print(f"  Risk Used: {Colors.YELLOW}₹{metrics.risk_used:,.2f}{Colors.END} / "
              f"₹{settings.max_daily_loss:,.2f}")
    else:
        print(f"  {Colors.YELLOW}No trades today{Colors.END}")
    
    print()


def print_open_positions(db):
    """Print current open positions"""
    open_trades = db.query(Trade).filter(
        Trade.status == TradeStatus.OPEN
    ).order_by(desc(Trade.entry_timestamp)).all()
    
    print(f"{Colors.BOLD}[OPEN POSITIONS] ({len(open_trades)}){Colors.END}")
    
    if open_trades:
        print(f"  {'Symbol':<12} {'Entry':<10} {'Current':<10} {'P&L':<12} {'R:R':<8} {'Time':<10}")
        print(f"  {'-'*70}")
        
        for trade in open_trades:
            # We'd need current price to calculate live P&L
            # For now, show entry details
            entry_time = trade.entry_timestamp.strftime('%H:%M:%S') if trade.entry_timestamp else '-'
            
            pnl_str = f"₹{trade.realized_pnl:,.2f}" if trade.realized_pnl else "Open"
            pnl_color = Colors.GREEN if trade.realized_pnl and trade.realized_pnl > 0 else Colors.WHITE
            
            print(f"  {Colors.BOLD}{trade.symbol:<12}{Colors.END} "
                  f"₹{trade.entry_price:<9.2f} "
                  f"{'--':<10} "
                  f"{pnl_color}{pnl_str:<12}{Colors.END} "
                  f"{'--':<8} "
                  f"{entry_time:<10}")
    else:
        print(f"  {Colors.YELLOW}No open positions{Colors.END}")
    
    print()


def print_recent_trades(db):
    """Print recent closed trades"""
    recent = db.query(Trade).filter(
        Trade.status == TradeStatus.CLOSED
    ).order_by(desc(Trade.exit_timestamp)).limit(5).all()
    
    print(f"{Colors.BOLD}[RECENT TRADES] (Last 5){Colors.END}")
    
    if recent:
        print(f"  {'Symbol':<12} {'Entry':<10} {'Exit':<10} {'P&L':<12} {'Result':<8} {'Time':<10}")
        print(f"  {'-'*70}")
        
        for trade in recent:
            exit_time = trade.exit_timestamp.strftime('%H:%M') if trade.exit_timestamp else '-'
            pnl = trade.realized_pnl if trade.realized_pnl else 0
            pnl_color = Colors.GREEN if pnl > 0 else Colors.RED
            result = "WIN" if pnl > 0 else "LOSS"
            result_color = Colors.GREEN if pnl > 0 else Colors.RED
            
            print(f"  {trade.symbol:<12} "
                  f"₹{trade.entry_price:<9.2f} "
                  f"₹{trade.exit_price if trade.exit_price else 0:<9.2f} "
                  f"{pnl_color}₹{pnl:<11.2f}{Colors.END} "
                  f"{result_color}{result:<8}{Colors.END} "
                  f"{exit_time:<10}")
    else:
        print(f"  {Colors.YELLOW}No trades yet{Colors.END}")
    
    print()


def print_live_quotes(quotes: Dict):
    """Print live market quotes"""
    print(f"{Colors.BOLD}[LIVE QUOTES]{Colors.END}")
    
    if quotes:
        print(f"  {'Symbol':<12} {'LTP':<10} {'Change':<12} {'High':<10} {'Low':<10}")
        print(f"  {'-'*60}")
        
        for symbol, quote in quotes.items():
            ltp = quote.get('ltp', 0)
            open_price = quote.get('open', ltp)
            change_pct = ((ltp - open_price) / open_price * 100) if open_price > 0 else 0
            change_color = Colors.GREEN if change_pct >= 0 else Colors.RED
            
            print(f"  {symbol:<12} "
                  f"₹{ltp:<9.2f} "
                  f"{change_color}{change_pct:>+6.2f}%{Colors.END}    "
                  f"₹{quote.get('high', 0):<9.2f} "
                  f"₹{quote.get('low', 0):<9.2f}")
    else:
        print(f"  {Colors.YELLOW}No quotes available{Colors.END}")
    
    print()


def print_strategy_status():
    """Print strategy activity from logs"""
    print(f"{Colors.BOLD}[STRATEGY ACTIVITY] (Last 5 decisions){Colors.END}")
    
    try:
        log_file = f"logs/trading_{now_ist().strftime('%Y-%m-%d')}.log"
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                strategy_lines = [l for l in lines if 'strategies.live_simple' in l and 'DEBUG' in l]
                recent = strategy_lines[-5:] if len(strategy_lines) >= 5 else strategy_lines
                
                for line in recent:
                    # Extract just the decision part
                    if ' - ' in line:
                        parts = line.split(' - ')
                        if len(parts) >= 4:
                            decision = parts[-1].strip()
                            print(f"  {Colors.CYAN}→{Colors.END} {decision}")
        else:
            print(f"  {Colors.YELLOW}No log file found{Colors.END}")
    except Exception as e:
        print(f"  {Colors.RED}Error reading logs: {e}{Colors.END}")
    
    print()


def print_footer():
    """Print dashboard footer"""
    print(f"{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"  Press Ctrl+C to exit | Auto-refresh every 5 seconds")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}\n")


async def fetch_live_data(broker):
    """Fetch live market data"""
    watchlist = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK']
    quotes = {}
    
    for symbol in watchlist:
        try:
            quote = await broker.get_quote(symbol)
            quotes[symbol] = {
                'ltp': quote.last_price,
                'open': quote.open,
                'high': quote.high,
                'low': quote.low,
                'volume': quote.volume
            }
        except Exception as e:
            quotes[symbol] = {'ltp': 0, 'open': 0, 'high': 0, 'low': 0, 'volume': 0}
    
    return quotes


async def main_loop():
    """Main monitoring loop"""
    # Initialize broker
    broker_name = settings.broker
    
    # Prepare broker config
    if broker_name == "zerodha":
        broker_config = {
            "api_key": settings.zerodha_api_key,
            "api_secret": settings.zerodha_api_secret,
            "user_id": settings.zerodha_user_id,
            "password": settings.zerodha_password,
            "totp_secret": settings.zerodha_totp_secret
        }
    else:  # groww
        broker_config = {
            "api_key": settings.groww_api_key,
            "api_secret": settings.groww_api_secret,
            "api_url": settings.groww_api_url
        }
    
    broker = BrokerFactory.create_broker(broker_name, broker_config)
    
    await broker.connect()
    
    try:
        while True:
            # Clear and redraw
            clear_screen()
            
            # Get database session
            db = SessionLocal()
            
            try:
                # Print all sections
                print_header()
                print_system_status(broker)
                
                # Fetch live data
                try:
                    margins = await broker.get_margins()
                    print_account_info(margins)
                except Exception as e:
                    print(f"{Colors.RED}Error fetching margins: {e}{Colors.END}\n")
                
                print_daily_metrics(db)
                print_open_positions(db)
                print_recent_trades(db)
                
                # Fetch live quotes
                quotes = await fetch_live_data(broker)
                print_live_quotes(quotes)
                
                print_strategy_status()
                print_footer()
                
            finally:
                db.close()
            
            # Wait before refresh
            await asyncio.sleep(5)
            
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Monitor stopped by user{Colors.END}\n")
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}\n")
    finally:
        # Cleanup
        try:
            if hasattr(broker, 'session') and broker.session:
                await broker.session.close()
        except:
            pass


def main():
    """Entry point"""
    try:
        asyncio.run(main_loop())
    except Exception as e:
        print(f"{Colors.RED}Fatal error: {e}{Colors.END}")


if __name__ == "__main__":
    main()
