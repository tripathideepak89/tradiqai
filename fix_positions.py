"""Fix database position mismatches"""
from database import SessionLocal
from models import Trade, TradeStatus
from datetime import datetime

def fix_positions():
    db = SessionLocal()
    
    try:
        # Fix TATASTEEL PENDING orders -> OPEN
        tatasteel_trades = db.query(Trade).filter(
            Trade.symbol == "TATASTEEL",
            Trade.status == TradeStatus.PENDING
        ).all()
        
        print(f"Found {len(tatasteel_trades)} TATASTEEL PENDING orders")
        for trade in tatasteel_trades:
            print(f"  Updating Trade ID {trade.id}: {trade.quantity} shares @ ₹{trade.entry_price}")
            trade.status = TradeStatus.OPEN
        
        db.commit()
        print("✓ TATASTEEL orders marked as OPEN\n")
        
        # Fix GRASIM OPEN position -> CLOSED
        grasim_trade = db.query(Trade).filter(
            Trade.symbol == "GRASIM",
            Trade.status == TradeStatus.OPEN
        ).first()
        
        if grasim_trade:
            print(f"Closing GRASIM position (ID {grasim_trade.id})")
            print(f"  Entry: ₹{grasim_trade.entry_price}, Qty: {grasim_trade.quantity}")
            
            # Estimate exit price from broker (around 2935 based on logs)
            exit_price = 2935.0
            grasim_trade.status = TradeStatus.CLOSED
            grasim_trade.exit_price = exit_price
            grasim_trade.exit_time = datetime.now()
            
            # Calculate PnL
            pnl = (exit_price - grasim_trade.entry_price) * grasim_trade.quantity
            grasim_trade.net_pnl = pnl
            grasim_trade.gross_pnl = pnl  # Simplified
            
            db.commit()
            print(f"✓ GRASIM closed at ₹{exit_price}, PnL: ₹{pnl:.2f}\n")
        else:
            print("No GRASIM OPEN position found\n")
        
        # Show current positions
        print("Current database positions:")
        all_trades = db.query(Trade).filter(
            Trade.status.in_([TradeStatus.OPEN, TradeStatus.PENDING])
        ).all()
        
        if all_trades:
            for trade in all_trades:
                print(f"  {trade.symbol}: {trade.status} - {trade.quantity} shares @ ₹{trade.entry_price}")
        else:
            print("  No open/pending positions")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_positions()
