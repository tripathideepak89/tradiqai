# AutoTrade AI 🤖

**Automated Equity Trading System for Indian Markets**

A production-ready algorithmic trading system for Indian equity markets with advanced risk management, multiple broker support, and comprehensive monitoring.

## 🎯 Features

- **Capital Management**: Designed for ₹50k capital with strict risk controls
- **Multiple Strategies**: Intraday & Swing trading strategies
- **Broker Support**: Zerodha Kite Connect & **Groww** (both fully supported)
- **Risk Management**: Multi-layered risk engine with daily loss limits
- **Real-time Monitoring**: Telegram alerts, health checks, kill switch
- **Paper Trading**: Test strategies without risking real capital
- **Position Reconciliation**: Automatic mismatch detection
- **Database Logging**: Complete audit trail of all trades and events

## 📊 Performance Targets

- **Monthly Return**: 3-6% realistic target
- **Max Drawdown**: Under 10-12%
- **Risk Per Trade**: Max ₹400
- **Daily Loss Limit**: ₹1,500 (3% of capital)
- **Max Open Positions**: 2 concurrent trades

## 🏗️ Architecture

```
Market Data → Strategy Engine → Risk Engine → Order Manager → Broker
                                      ↓
                              Monitoring Service
```

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optional)
- Zerodha Kite Connect API credentials

## 🚀 Quick Start

### 1. Clone and Setup

```bash
cd autotrade-ai
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note**: TA-Lib requires system-level installation:
- Windows: Download from https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
- Linux: `sudo apt-get install ta-lib`
- Mac: `brew install ta-lib`

### 3. Configuration

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Trading Configuration
INITIAL_CAPITAL=50000
PAPER_TRADING=true  # Start with paper trading

# Broker Selection
BROKER=zerodha  # or groww

# Zerodha Credentials (if using Zerodha)
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
ZERODHA_USER_ID=your_user_id

# Groww Credentials (if using Groww) 
GROWW_API_KEY=your_jwt_token
GROWW_API_SECRET=your_api_secret

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/autotrade
REDIS_URL=redis://localhost:6379/0

# Telegram Alerts
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 4. Database Setup

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Initialize database
python -c "from database import init_db; init_db()"
```

### 5. Run the System

```bash
python main.py
```

## 🐳 Docker Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop system
docker-compose down
```

## 📁 Project Structure

```
autotrade-ai/
├── brokers/              # Broker adapters (Zerodha, Groww)
│   ├── base.py          # Abstract broker interface
│   ├── zerodha.py       # Zerodha implementation
│   ├── groww.py         # Groww implementation
│   └── factory.py       # Broker factory
├── strategies/          # Trading strategies
│   ├── base.py          # Base strategy class
│   ├── intraday.py      # Intraday EMA pullback
│   └── swing.py         # Swing breakout
├── config.py            # Configuration management
├── database.py          # Database connection
├── models.py            # SQLAlchemy models
├── risk_engine.py       # Risk management engine
├── order_manager.py     # Order execution & tracking
├── monitoring.py        # Alerts & health checks
├── main.py              # Main application
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker image
├── docker-compose.yml  # Docker orchestration
└── .env.example        # Configuration template
```

## 🎛️ Risk Management Rules

| Rule | Value |
|------|-------|
| Max Daily Loss | ₹1,500 (3%) |
| Max Per Trade Risk | ₹400 |
| Max Open Trades | 2 |
| Max Capital Per Trade | ₹12,500 |
| Max Exposure | 80% of capital |
| Consecutive Loss Limit | 3 trades |

These rules are enforced by the Risk Engine before every trade.

## 📈 Strategies

### Intraday Strategy
- **Timeframe**: 15 minutes
- **Entry**: EMA pullback (20 EMA > 50 EMA)
- **Exit**: Target (1.5R) or trailing stop
- **Filter**: Volume > 1.5x average, NIFTY trend

### Swing Strategy
- **Timeframe**: Daily
- **Entry**: Breakout above 20-day high
- **Exit**: Close below 10 EMA or 5 days
- **Filter**: Volume spike > 1.5x

## 🔔 Monitoring & Alerts

The system sends Telegram alerts for:
- Trade entries & exits
- Risk limit warnings
- Daily P&L summary
- System errors
- Kill switch activation

## 🛡️ Safety Mechanisms

1. **Kill Switch**: Manual emergency stop
2. **Daily Loss Limit**: Auto-halt at 3% loss
3. **Position Reconciliation**: Every 10 seconds
4. **Market Hours Check**: No trading outside 9:15-15:30
5. **Consecutive Loss Limit**: Pause after 3 losses

## 📊 Backtesting

```python
# TODO: Implement backtesting framework
# Requirements:
# - 3+ years historical data
# - Simulate: brokerage, STT, slippage
# - Metrics: Win rate, Sharpe, Max DD
```

## 🔧 Development

### Run Tests
```bash
pytest tests/
```

### Code Quality
```bash
black .
flake8 .
```

### Database Migrations
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## 📝 Important Notes

⚠️ **Before Going Live:**

1. ✅ Complete 30+ paper trades successfully
2. ✅ Backtest with 3+ years data
3. ✅ Verify profit factor > 1.3
4. ✅ Test kill switch functionality
5. ✅ Verify position reconciliation
6. ✅ Test with minimal capital first

⚠️ **Broker Notes:**
- **Groww**: Fully implemented (see GROWW_SETUP.md)
- **Zerodha**: Requires access token management

⚠️ **Zerodha Login:**
- Automated login requires access token
- Implement headless browser for auto-login
- Or manually provide access token daily

## 🤝 Contributing

This is a personal trading system. Use at your own risk.

## ⚖️ Disclaimer

**Trading involves substantial risk of loss. Past performance is not indicative of future results. This software is provided "as is" without warranty. Use at your own risk.**

- Not financial advice
- Test thoroughly before live trading
- Start with paper trading
- Never risk more than you can afford to lose

## 📄 License

MIT License - See LICENSE file

## 📞 Support

For issues and questions:
- Check logs in `logs/` directory
- Review system logs in database
- Monitor Telegram alerts
- Check Redis for real-time state

## 🎓 Resources

- [Zerodha Kite Connect Docs](https://kite.trade/docs/connect/v3/)
- [TA-Lib Documentation](https://mrjbq7.github.io/ta-lib/)
- [Algorithmic Trading Guide](https://www.investopedia.com/articles/active-trading/101014/basics-algorithmic-trading-concepts-and-examples.asp)

---

**Built with ❤️ for algorithmic trading in Indian markets**
