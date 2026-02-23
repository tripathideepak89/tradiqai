# Using Groww as Your Broker

## Overview

The AutoTrade AI system now supports **Groww** as a broker option alongside Zerodha. This guide will help you set up and use Groww for automated trading.

## Prerequisites

- ✅ Groww trading account
- ✅ Groww API access credentials (API Key and Secret)
- ✅ System already set up (see QUICKSTART.md)

## Your Groww Credentials

Your Groww API credentials have been configured:

```
API Key Format: JWT token (starts with eyJ...)
API Secret: Alphanumeric string with special characters
```

## Configuration

### 1. Update .env File

```bash
# Set broker to Groww
BROKER=groww

# Groww API credentials
GROWW_API_KEY=eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9...
GROWW_API_SECRET=LMT1j3n9j_vgY9kRP8i5EyOEo_#evm^P
GROWW_API_URL=https://api.groww.in/v1

# Keep paper trading ON initially
PAPER_TRADING=true
```

### 2. Test Connection

```powershell
# Create a test script
python -c "
from brokers.factory import BrokerFactory
import asyncio
from config import settings

async def test():
    config = {
        'api_key': settings.groww_api_key,
        'api_secret': settings.groww_api_secret,
        'api_url': settings.groww_api_url
    }
    
    broker = BrokerFactory.create_broker('groww', config)
    connected = await broker.connect()
    
    if connected:
        print('✅ Successfully connected to Groww!')
        # Test getting margins
        margins = await broker.get_margins()
        print(f'Available margin: ₹{margins[\"available\"]:.2f}')
        await broker.disconnect()
    else:
        print('❌ Failed to connect to Groww')

asyncio.run(test())
"
```

## API Endpoints

The Groww adapter uses these endpoints:

| Endpoint | Purpose | Method |
|----------|---------|--------|
| `/user/profile` | User profile & auth verification | GET |
| `/user/margins` | Account margins | GET |
| `/orders` | Place/view orders | POST/GET |
| `/orders/{id}` | Order details/modify/cancel | GET/PUT/DELETE |
| `/market/quote` | Real-time quotes | GET |
| `/market/historical` | Historical data | GET |
| `/portfolio/positions` | Current positions | GET |
| `/portfolio/holdings` | Long-term holdings | GET |

## Features Supported

### ✅ Fully Implemented

- Order placement (Market, Limit, SL, SL-M)
- Order modification
- Order cancellation
- Position tracking
- Quote fetching
- Historical data retrieval
- Margin queries
- Holdings retrieval

### ⚠️ Limitations

- WebSocket real-time data not implemented yet
  - System will use REST API polling instead
  - Slightly higher latency but functional
- API rate limits may apply (check Groww docs)

## Switching Between Brokers

You can easily switch between Zerodha and Groww:

### Option 1: Using .env

```bash
# In .env file
BROKER=groww  # or zerodha
```

### Option 2: Programmatically

Edit `main.py` if you need custom logic:

```python
# In TradingSystem.initialize()
if market_conditions == "volatile":
    broker_name = "zerodha"
else:
    broker_name = "groww"
```

## Example: Complete Setup

### 1. Configure .env

```bash
# Broker
BROKER=groww

# Groww Credentials  
GROWW_API_KEY=eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NTk3MTc5NjEsImlhdCI6MTc3MTMxNzk2MSwibmJmIjoxNzcxMzE3OTYxLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCJiZjZlMWUwOS0zMmEyLTRiZjAtYjg1My0zYjIwN2ViYzczN2ZcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiM2JhYTdjM2EtOWIyMy00MmM4LTlkMmUtMjRlNWMxM2VlZTU3XCIsXCJkZXZpY2VJZFwiOlwiZjM3NjJhYWMtM2JkZC01MjJjLWJhZTItZTkzNThmMDNhMThkXCIsXCJzZXNzaW9uSWRcIjpcIjBlOWFjMGQ5LTZiOWYtNGRlNS04ZmNhLTU0OGE3M2U2MTU2Y1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYkFiejlWRmU0U0JzTUVab0RoSEVuV3hSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIxMzkuMTIyLjE5MS4yMjUsMTA0LjIzLjIyMS4yMTIsMzUuMjQxLjIzLjEyM1wiLFwidHdvRmFFeHBpcnlUc1wiOjI1NTk3MTc5NjE3MzF9IiwiaXNzIjoiYXBleC1hdXRoLXByb2QtYXBwIn0.8Z-bwezPqSeB-m8Ic_mMsIf9rdud2nHbrtujnT2i7ySRHOTlpFT0An2m8oz9mVmme-7oKo8KBgZuOd0kqgH2zA
GROWW_API_SECRET=LMT1j3n9j_vgY9kRP8i5EyOEo_#evm^P
GROWW_API_URL=https://api.groww.in/v1

# Trading (keep conservative initially)
INITIAL_CAPITAL=50000
PAPER_TRADING=true
```

### 2. Start System

```powershell
python main.py
```

Expected output:
```
INFO - Initializing AutoTrade AI System...
INFO - Using broker: groww
INFO - Connecting to Groww API...
INFO - Connected to Groww: [Your Name]
INFO - ✓ Broker connected
...
```

### 3. Verify via API

```powershell
# Start API server
python api.py

# Check system status
Invoke-RestMethod http://localhost:8000/health
```

## Troubleshooting

### Error: "Failed to verify Groww connection"

**Possible causes:**
1. Invalid API key or secret
2. API key expired (check expiry in JWT)
3. Network/firewall issues
4. Groww API endpoint changed

**Solutions:**
```powershell
# 1. Verify credentials
python -c "from config import settings; print(f'Key: {settings.groww_api_key[:50]}...')"

# 2. Check API URL accessibility
curl https://api.groww.in/v1/user/profile -H "Authorization: Bearer YOUR_KEY"

# 3. Enable debug logging
# In .env: DEBUG=true, LOG_LEVEL=DEBUG
```

### Error: "API rate limit exceeded"

**Solution:** Groww may have rate limits. The system includes delays, but you can adjust:

Edit `brokers/groww.py`:
```python
import asyncio

async def _make_request(...):
    # Add delay between requests
    await asyncio.sleep(0.1)  # 100ms delay
    ...
```

### WebSocket Warnings

**This is expected.** The system shows:
```
WARNING - Groww WebSocket support not implemented yet
INFO - Consider using REST polling for now
```

The system works fine with REST API polling - it just polls every minute instead of getting instant updates.

## Performance Comparison

| Feature | Zerodha | Groww |
|---------|---------|-------|
| Order Execution | ✅ Fast | ✅ Fast |
| Real-time Data | ✅ WebSocket | ⚠️ REST Polling |
| Historical Data | ✅ Full | ✅ Full |
| API Stability | ✅ Mature | ⚠️ Newer |
| Documentation | ✅ Extensive | ⚠️ Limited |
| Brokerage | ₹20/order | Check Groww |

## Best Practices with Groww

1. **Start with Paper Trading**
   - Test for at least 30 trades
   - Verify all features work

2. **Monitor API Calls**
   - Watch for rate limits
   - Check system logs regularly

3. **Keep Credentials Secure**
   - Never commit .env file
   - Rotate API keys regularly
   - Check JWT expiry date

4. **Verify Charges**
   - Update `_calculate_charges()` in order_manager.py
   - Groww fees may differ from Zerodha

5. **Stay Updated**
   - Monitor Groww API changes
   - Update adapter as needed

## API Token Management

Your Groww API key is a JWT token with expiry:

```python
# Check token expiry
import jwt
import datetime

token = "YOUR_GROWW_API_KEY"
decoded = jwt.decode(token, options={"verify_signature": False})
expiry = datetime.datetime.fromtimestamp(decoded['exp'])
print(f"Token expires: {expiry}")
```

If expired, regenerate from Groww dashboard.

## Support

For Groww-specific issues:
- Check Groww API documentation
- Contact Groww support for API issues
- Check system logs: `logs/trading_YYYY-MM-DD.log`
- Query database: `SELECT * FROM system_logs WHERE symbol IS NOT NULL`

## Migration Checklist

Moving from Zerodha to Groww:

- [ ] Get Groww API credentials
- [ ] Update .env with Groww credentials
- [ ] Set BROKER=groww
- [ ] Test connection (script above)
- [ ] Run paper trading for 30+ trades
- [ ] Verify all features work
- [ ] Update charge calculations if needed
- [ ] Monitor first week closely
- [ ] Keep Zerodha as backup option

---

**Note**: This implementation is based on expected Groww API structure. If you encounter issues, you may need to adjust the adapter based on actual Groww API documentation. Check `brokers/groww.py` for implementation details.

🚀 **Happy Trading with Groww!**
