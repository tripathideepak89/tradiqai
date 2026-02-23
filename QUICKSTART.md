# TradiqAI - Quick Start Guide

## Prerequisites Checklist

Before you begin, ensure you have:

- [ ] Python 3.11+ installed
- [ ] PostgreSQL 15+ installed and running
- [ ] Redis 7+ installed and running
- [ ] Zerodha Kite Connect account with API access
- [ ] Telegram bot (optional, for alerts)

## Installation Steps

### 1. Clone/Download the Project

```powershell
cd c:\Users\dtrid8\development\autotrade-ai
```

### 2. Run Setup Script

```powershell
python setup.py
```

This will:
- Check Python version
- Create necessary directories
- Create .env file from template
- Install dependencies (if you choose)

### 3. Configure Environment

Edit `.env` file with your credentials:

```bash
# CRITICAL: Set paper trading to true initially
PAPER_TRADING=true

# Zerodha credentials
ZERODHA_API_KEY=your_api_key_here
ZERODHA_API_SECRET=your_api_secret_here
ZERODHA_USER_ID=your_user_id_here

# Database (if using Docker, these are correct)
DATABASE_URL=postgresql://postgres:password@localhost:5432/autotrade
REDIS_URL=redis://localhost:6379/0

# Telegram alerts (optional but recommended)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 4. Start Infrastructure

#### Option A: Using Docker (Recommended)

```powershell
# Start only PostgreSQL and Redis
docker-compose up -d postgres redis

# Wait for services to be healthy (about 10 seconds)
Start-Sleep -Seconds 10
```

#### Option B: Manual Installation

Install PostgreSQL and Redis manually and ensure they're running on default ports.

### 5. Initialize Database

```powershell
python -c "from database import init_db; init_db()"
```

You should see: `Database tables created successfully`

### 6. Test the System

```powershell
# Check system status
python cli.py status

# View performance metrics (will be empty initially)
python cli.py performance

# Check system logs
python cli.py logs
```

### 7. Start the Trading System

```powershell
# Make sure it's in PAPER_TRADING mode!
python main.py
```

You should see:
```
INFO - Initializing TradiqAI System...
INFO - ✓ Database initialized
INFO - ✓ Broker connected
INFO - ✓ Risk engine initialized
...
```

## Common Issues & Solutions

### Issue: "Access token not available"

**Solution**: Zerodha requires manual login for access token generation. 

Two options:
1. **Simple**: Manually get access token daily and add to .env
2. **Advanced**: Implement automated login with Selenium (not included)

### Issue: "Failed to connect to database"

**Solution**: 
1. Check PostgreSQL is running: `docker ps` or check Task Manager
2. Verify DATABASE_URL in .env is correct
3. Try: `docker-compose restart postgres`

### Issue: "Redis connection refused"

**Solution**:
1. Check Redis is running: `docker ps`
2. Verify REDIS_URL in .env is correct
3. Try: `docker-compose restart redis`

### Issue: "TA-Lib installation failed"

**Solution**:
- Windows: Download wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
- Install with: `pip install TA_Lib-0.4.28-cp311-cp311-win_amd64.whl`

## Testing Workflow

### Phase 1: Paper Trading (Weeks 1-2)

1. Run system in PAPER_TRADING mode
2. Monitor for at least 30 trades
3. Check metrics: `python cli.py performance`
4. Analyze logs: `python cli.py logs`

### Phase 2: Small Capital (Weeks 3-4)

1. Set PAPER_TRADING=false
2. Reduce INITIAL_CAPITAL to minimum (e.g., 10000)
3. Run for 20+ trades
4. Verify all safety mechanisms work

### Phase 3: Full Capital (After confidence)

1. Set INITIAL_CAPITAL=50000
2. Monitor closely for first week
3. Review daily summaries

## API Usage

Start the API server:

```powershell
python api.py
```

Access API documentation: http://localhost:8000/docs

Example API calls:

```powershell
# Get system health
Invoke-RestMethod http://localhost:8000/health

# Get open trades
Invoke-RestMethod http://localhost:8000/trades/open

# Get today's metrics
Invoke-RestMethod http://localhost:8000/metrics/today

# Activate kill switch
Invoke-RestMethod -Method POST http://localhost:8000/monitoring/kill-switch/activate `
  -ContentType "application/json" `
  -Body '{"reason": "Emergency stop"}'
```

## CLI Commands Reference

```powershell
# System status
python cli.py status

# Recent trades
python cli.py trades --days 7

# Performance metrics
python cli.py performance

# System logs
python cli.py logs

# Activate/deactivate kill switch
python cli.py kill-switch
```

## Daily Operations Checklist

### Morning (Before Market Open)

- [ ] Check system status: `python cli.py status`
- [ ] Verify kill switch is inactive
- [ ] Check yesterday's performance
- [ ] Ensure PostgreSQL and Redis are running
- [ ] Start trading system: `python main.py`

### During Market Hours

- [ ] Monitor Telegram alerts
- [ ] Check open positions periodically
- [ ] Watch for risk limit warnings

### Evening (After Market Close)

- [ ] Review day's performance: `python cli.py performance`
- [ ] Check system logs for any errors
- [ ] Verify all positions closed (for intraday)
- [ ] Review Telegram daily summary

## Emergency Procedures

### Kill Switch Activation

If something goes wrong:

```powershell
# CLI
python cli.py kill-switch

# API
Invoke-RestMethod -Method POST http://localhost:8000/monitoring/kill-switch/activate `
  -ContentType "application/json" `
  -Body '{"reason": "Emergency"}'
```

This will:
- Stop all new trades immediately
- Alert via Telegram
- Keep existing positions (you need to close manually if needed)

### Manual Position Close

Currently requires using Zerodha Kite web/app directly or implementing close via order manager.

## Monitoring Best Practices

1. **Set up Telegram alerts** (highly recommended)
2. **Check system health** every few hours
3. **Review logs daily** for patterns or issues
4. **Monitor risk metrics** - don't let them approach limits
5. **Keep paper trading logs** for comparison

## Customization

### Add Your Watchlist

Edit `main.py` → `get_watchlist()` method:

```python
async def get_watchlist(self) -> List[str]:
    return ["RELIANCE", "TCS", "INFY", "YOUR_STOCKS"]
```

### Adjust Risk Parameters

Edit `.env`:

```bash
MAX_DAILY_LOSS=1500
MAX_PER_TRADE_RISK=400
MAX_OPEN_TRADES=2
```

### Modify Strategy Parameters

Edit strategy files in `strategies/` directory.

## Support & Resources

- **Documentation**: See README.md
- **System Logs**: `logs/` directory
- **Database Logs**: Query `system_logs` table
- **Zerodha API Docs**: https://kite.trade/docs/connect/v3/

## Success Metrics

Track these weekly:

- Win rate (target: >50%)
- Profit factor (target: >1.3)
- Max drawdown (target: <12%)
- Average R multiple (target: >1.5)
- Consecutive losses (should reset before limit)

---

**Remember**: 
- Start with PAPER_TRADING=true
- Never risk more than you can afford to lose
- Trading involves substantial risk
- This is not financial advice

Good luck! 🚀
