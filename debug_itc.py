"""Debug ITC signal execution"""
import asyncio
from database import SessionLocal
from brokers.groww import GrowwBroker
from risk_engine import RiskEngine
from order_manager import OrderManager
from strategies.live_simple import LiveSimpleStrategy
from config import settings

async def test_itc():
    db = SessionLocal()
    
    # Setup components
    broker_config = {
        "api_key": settings.groww_api_key,
        "api_secret": settings.groww_api_secret,
        "jwt_token": settings.groww_jwt_token
    }
    broker = GrowwBroker(broker_config)
    risk_engine = RiskEngine(broker=broker, db_session=db)
    order_manager = OrderManager(broker=broker, risk_engine=risk_engine, db_session=db)
    
    # Update capital
    await risk_engine.update_available_capital()
    print(f"Available capital: Rs {risk_engine.available_capital:.2f}")
    
    # Get ITC quote
    quote = await broker.get_quote("ITC")
    print(f"\nITC Quote:")
    print(f"  LTP: Rs {quote.last_price}")
    print(f"  Open: Rs {quote.open_price}")
    print(f"  High: Rs {quote.high}")
    print(f"  Low: Rs {quote.low}")
    
    # Check momentum
    momentum = ((quote.last_price - quote.open_price) / quote.open_price) * 100
    print(f"  Momentum: {momentum:+.2f}%")
    
    # Test strategy
    strategy = LiveSimpleStrategy()
    signal = await strategy.analyze(quote)
    
    if signal:
        print(f"\n✓ Signal generated:")
        print(f"  Action: {signal.action}")
        print(f"  Entry: Rs {signal.entry_price}")
        print(f"  Stop: Rs {signal.stop_loss}")
        print(f"  Target: Rs {signal.target}")
        print(f"  Confidence: {signal.confidence:.2f}")
        print(f"  Reason: {signal.reason}")
        
        # Try to execute
        print(f"\nTrying to execute signal...")
        result = await order_manager.execute_signal(signal, "LiveSimple")
        
        if result:
            print(f"✓ Order placed successfully: Trade ID {result.id}")
        else:
            print(f"✗ Order execution failed (check logs above for reason)")
    else:
        print(f"\n✗ No signal generated (insufficient momentum or other filters)")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(test_itc())
