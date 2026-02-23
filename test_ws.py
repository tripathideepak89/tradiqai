import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:9000/ws"
    try:
        print(f"Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!")
            
            # Wait for first message
            print("Waiting for data...")
            message = await asyncio.wait_for(websocket.recv(), timeout=15)
            data = json.loads(message)
            
            print(f"\n📊 Received data:")
            print(f"  - Account capital: {data.get('account', {}).get('capital', 0)}")
            print(f"  - Positions: {len(data.get('positions', []))}")
            print(f"  - Monitored stocks: {len(data.get('monitored_stocks', []))}")
            print(f"  - Trades: {len(data.get('trades', []))}")
            print(f"  - Market open: {data.get('market_open', False)}")
            
            if data.get('monitored_stocks'):
                print(f"\n📈 First monitored stock:")
                print(f"  {json.dumps(data['monitored_stocks'][0], indent=2)}")
            
    except asyncio.TimeoutError:
        print("❌ Timeout waiting for connection or data")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
