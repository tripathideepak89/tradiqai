"""Command-line interface for manual control"""
import asyncio
import click
from datetime import date
from sqlalchemy import func

from database import SessionLocal
from models import Trade, DailyMetrics, SystemLog
from risk_engine import RiskEngine
from monitoring import MonitoringService


@click.group()
def cli():
    """AutoTrade AI - Command Line Interface"""
    pass


@cli.command()
def status():
    """Show system status"""
    db = SessionLocal()
    monitoring = MonitoringService()
    
    try:
        click.echo("\n" + "="*60)
        click.echo("SYSTEM STATUS")
        click.echo("="*60)
        
        # Open positions
        open_trades = db.query(Trade).filter(
            Trade.status == "open"
        ).count()
        click.echo(f"Open Positions: {open_trades}")
        
        # Today's metrics
        today = date.today()
        metrics = db.query(DailyMetrics).filter(
            func.date(DailyMetrics.date) == today
        ).first()
        
        if metrics:
            click.echo(f"\nToday's P&L: ₹{metrics.net_pnl:.2f}")
            click.echo(f"Trades Taken: {metrics.trades_taken}")
            click.echo(f"Win Rate: {metrics.win_rate:.1f}%")
        
        # Risk metrics
        risk_engine = RiskEngine(db)
        risk_metrics = asyncio.run(risk_engine.get_risk_metrics())
        
        click.echo(f"\nDaily Loss: ₹{risk_metrics.get('daily_loss', 0):.2f} / ₹{risk_metrics.get('daily_loss_limit', 0):.2f}")
        click.echo(f"Consecutive Losses: {risk_metrics.get('consecutive_losses', 0)}")
        click.echo(f"Current Exposure: ₹{risk_metrics.get('current_exposure', 0):,.0f}")
        
        # Kill switch
        is_halted = monitoring.is_kill_switch_active()
        click.echo(f"\nKill Switch: {'🔴 ACTIVE' if is_halted else '🟢 Inactive'}")
        
        if is_halted:
            reason = monitoring.get_kill_switch_reason()
            click.echo(f"Reason: {reason}")
        
        click.echo("="*60 + "\n")
        
    finally:
        db.close()


@cli.command()
@click.option('--days', default=7, help='Number of days to show')
def trades(days):
    """Show recent trades"""
    db = SessionLocal()
    
    try:
        recent_trades = db.query(Trade).order_by(
            Trade.created_at.desc()
        ).limit(days * 5).all()
        
        click.echo("\n" + "="*100)
        click.echo("RECENT TRADES")
        click.echo("="*100)
        click.echo(f"{'Symbol':<12} {'Strategy':<20} {'Entry':<10} {'Exit':<10} {'P&L':<10} {'Status':<10}")
        click.echo("-"*100)
        
        for trade in recent_trades:
            pnl = f"₹{trade.net_pnl:.2f}" if trade.net_pnl else "N/A"
            exit_price = f"₹{trade.exit_price:.2f}" if trade.exit_price else "N/A"
            
            click.echo(
                f"{trade.symbol:<12} {trade.strategy_name:<20} "
                f"₹{trade.entry_price:<8.2f} {exit_price:<10} {pnl:<10} {trade.status.value:<10}"
            )
        
        click.echo("="*100 + "\n")
        
    finally:
        db.close()


@cli.command()
def kill_switch():
    """Activate kill switch"""
    monitoring = MonitoringService()
    
    if monitoring.is_kill_switch_active():
        click.echo("⚠️  Kill switch is already active")
        reason = monitoring.get_kill_switch_reason()
        click.echo(f"Reason: {reason}")
        
        if click.confirm("Do you want to deactivate it?"):
            monitoring.deactivate_kill_switch()
            click.echo("✅ Kill switch deactivated")
    else:
        if click.confirm("⚠️  This will stop all trading. Continue?"):
            reason = click.prompt("Reason", default="Manual activation")
            monitoring.activate_kill_switch(reason)
            click.echo("🔴 Kill switch activated")


@cli.command()
@click.argument('trade_id', type=int)
def close_trade(trade_id):
    """Close a specific trade"""
    if not click.confirm(f"Close trade {trade_id}?"):
        return
    
    # This requires the full system to be running
    click.echo("⚠️  Use the API or monitoring interface to close trades")
    click.echo("This CLI command is for information only")


@cli.command()
def logs():
    """Show recent system logs"""
    db = SessionLocal()
    
    try:
        recent_logs = db.query(SystemLog).order_by(
            SystemLog.timestamp.desc()
        ).limit(50).all()
        
        click.echo("\n" + "="*120)
        click.echo("SYSTEM LOGS")
        click.echo("="*120)
        
        for log in recent_logs:
            severity_color = {
                'DEBUG': 'white',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red'
            }.get(log.severity, 'white')
            
            click.echo(
                f"{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')} "
                f"[{click.style(log.severity, fg=severity_color)}] "
                f"{log.event_type}: {log.message}"
            )
        
        click.echo("="*120 + "\n")
        
    finally:
        db.close()


@cli.command()
def performance():
    """Show performance metrics"""
    db = SessionLocal()
    
    try:
        # Get all closed trades
        closed_trades = db.query(Trade).filter(
            Trade.status == "closed"
        ).all()
        
        if not closed_trades:
            click.echo("No closed trades yet")
            return
        
        total_trades = len(closed_trades)
        winners = [t for t in closed_trades if t.net_pnl > 0]
        losers = [t for t in closed_trades if t.net_pnl <= 0]
        
        total_pnl = sum(t.net_pnl for t in closed_trades)
        win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0
        
        click.echo("\n" + "="*60)
        click.echo("PERFORMANCE METRICS")
        click.echo("="*60)
        click.echo(f"Total Trades:    {total_trades}")
        click.echo(f"Winners:         {len(winners)} ({win_rate:.1f}%)")
        click.echo(f"Losers:          {len(losers)}")
        click.echo(f"\nTotal P&L:       ₹{total_pnl:,.2f}")
        
        if winners:
            avg_win = sum(t.net_pnl for t in winners) / len(winners)
            largest_win = max(t.net_pnl for t in winners)
            click.echo(f"Average Win:     ₹{avg_win:.2f}")
            click.echo(f"Largest Win:     ₹{largest_win:.2f}")
        
        if losers:
            avg_loss = sum(t.net_pnl for t in losers) / len(losers)
            largest_loss = min(t.net_pnl for t in losers)
            click.echo(f"Average Loss:    ₹{avg_loss:.2f}")
            click.echo(f"Largest Loss:    ₹{largest_loss:.2f}")
        
        click.echo("="*60 + "\n")
        
    finally:
        db.close()


if __name__ == "__main__":
    cli()
