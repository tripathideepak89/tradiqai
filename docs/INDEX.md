# TradiqAI Documentation

Welcome to the **TradiqAI** documentation! This is your complete guide to understanding, deploying, and operating an intelligent algorithmic trading system designed specifically for Indian equity markets.

## 🚀 What is TradiqAI?

TradiqAI is a production-ready algorithmic trading system that combines advanced risk management, cost-aware execution, and intelligent automation to trade Indian equities on NSE/BSE exchanges.

### Key Highlights

- **💰 Cost-Aware Trading**: Every trade validated against transaction costs before execution
- **🛡️ Multi-Layer Risk Management**: 7-checkpoint risk engine protecting your capital
- **📊 Performance Tracking**: 0-100 scoring system with automated rebalancing
- **🔌 Multi-Broker Support**: Works with Zerodha and Groww
- **📈 Real-Time Dashboard**: Live monitoring with WebSocket updates
- **🤖 Automated Intelligence**: News impact detection and market regime analysis

## 📚 Quick Navigation

### New to TradiqAI?

Start here to get up and running quickly:

1. [Quick Start Guide](QUICKSTART.md) - Get trading in under 10 minutes
2. [System Architecture](ARCHITECTURE.md) - Understand how everything works
3. [Broker Setup - Groww](GROWW_SETUP.md) - Configure your broker connection

### Already Familiar?

Jump directly to what you need:

- [Trade Flows](TRADE_FLOWS.md) - Complete trade lifecycle documentation
- [Cost-Aware System](COST_AWARE_SYSTEM.md) - Transaction cost validation details
- [Deployment Guide](DEPLOYMENT.md) - Production deployment instructions
- [Dashboard Setup](DASHBOARD.md) - Configure web monitoring interface

## 🎯 System Capabilities

### Capital Management
- Designed for ₹50,000 starting capital
- Dynamic allocation across 4 time layers (Intraday, Swing, Mid, Long)
- Performance-based monthly rebalancing

### Risk Controls
- Max ₹400 risk per trade (0.8% of capital)
- Daily loss limit: ₹1,500 (3% of capital)
- Maximum 2 concurrent open positions
- Total exposure capped at 80%
- Automatic kill switch on consecutive losses

### Cost Philosophy
- Expected move must be ≥2x transaction cost
- Cost ratio must be ≤25% of expected profit
- Net profit must be positive after all fees
- Quality-first approach prevents micro-scalping

### Performance Targets
- Monthly Return: 3-6% realistic target
- Max Drawdown: Under 10-12%
- Win Rate: Maintain above 50%
- Profit Factor: Target above 1.5

## 📖 Documentation Structure

### 📘 Core Documentation

| Document | Description | Read Time |
|----------|-------------|-----------|
| [README](README.md) | Project overview and features | 5 min |
| [QUICKSTART](QUICKSTART.md) | Get started in 10 minutes | 10 min |
| [ARCHITECTURE](ARCHITECTURE.md) | Complete system architecture | 20 min |
| [TRADE_FLOWS](TRADE_FLOWS.md) | Trade lifecycle and state management | 15 min |

### 🔧 Setup & Configuration

| Document | Description | Read Time |
|----------|-------------|-----------|
| [GROWW_SETUP](GROWW_SETUP.md) | Configure Groww broker | 15 min |
| [TELEGRAM_SETUP](TELEGRAM_SETUP.md) | Enable Telegram alerts | 10 min |
| [DASHBOARD](DASHBOARD.md) | Web dashboard configuration | 10 min |
| [DEPLOYMENT](DEPLOYMENT.md) | Production deployment | 30 min |

### 💡 Advanced Topics

| Document | Description | Read Time |
|----------|-------------|-----------|
| [COST_AWARE_SYSTEM](COST_AWARE_SYSTEM.md) | Transaction cost validation | 15 min |
| [DOCUMENTATION_INDEX](DOCUMENTATION_INDEX.md) | Complete diagram catalog | 10 min |
| [LIVE_IMPLEMENTATION](LIVE_IMPLEMENTATION.md) | Live trading guide | 20 min |
| [GIT_COMMIT_VERIFICATION](GIT_COMMIT_VERIFICATION.md) | Git workflow and security | 5 min |

## 🎨 Visual Documentation

TradiqAI includes **22 professional Mermaid diagrams** (1600+ lines) covering:

- High-level architecture
- Trade execution flows
- Cost-aware filtering
- Risk management checkpoints
- Performance tracking algorithms
- News impact detection
- Database schemas
- State machines
- Deployment architecture

[View Complete Diagram Catalog →](DOCUMENTATION_INDEX.md)

## 🛠️ Technology Stack

- **Language**: Python 3.11+
- **Web Framework**: FastAPI
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **Technical Analysis**: TA-Lib
- **Containerization**: Docker & Kubernetes
- **ORM**: SQLAlchemy
- **API**: Zerodha Kite Connect, Groww API

## 🔗 Quick Links

- **Main Site**: [tradiqai.com](https://tradiqai.com)
- **Dashboard**: [dashboard.tradiqai.com](https://dashboard.tradiqai.com)
- **GitHub**: [github.com/tripathideepak89/TradiqAI](https://github.com/tripathideepak89/TradiqAI)
- **Issues**: [GitHub Issues](https://github.com/tripathideepak89/TradiqAI/issues)

## 💬 Support

### Getting Help

- **Documentation**: You're already here!
- **GitHub Issues**: Report bugs or request features
- **Community**: Join discussions on GitHub
- **Email**: support@tradiqai.com (if configured)

### Common Questions

**Q: Is this safe for real money trading?**  
A: TradiqAI includes paper trading mode for testing. Always start with paper trading and verify the system works as expected before using real capital.

**Q: Which broker should I use?**  
A: Both Zerodha and Groww are fully supported. Groww is recommended for beginners due to simpler API setup.

**Q: Do I need programming knowledge?**  
A: Basic understanding of Python and trading concepts helps, but detailed documentation guides you through setup and configuration.

**Q: What are the minimum requirements?**  
A: Python 3.11+, PostgreSQL 15+, Redis 7+, and ₹50,000 capital (recommended minimum).

## 🎓 Learning Path

### For Traders (No Programming Background)

1. Read [README](README.md) for overview
2. Follow [QUICKSTART](QUICKSTART.md) step-by-step
3. Review [ARCHITECTURE](ARCHITECTURE.md) Diagram #1 (High-level)
4. Study [COST_AWARE_SYSTEM](COST_AWARE_SYSTEM.md) philosophy
5. Set up [DASHBOARD](DASHBOARD.md) for monitoring

### For Developers

1. Review [ARCHITECTURE](ARCHITECTURE.md) completely
2. Study [TRADE_FLOWS](TRADE_FLOWS.md) state machines
3. Examine [GIT_COMMIT_VERIFICATION](GIT_COMMIT_VERIFICATION.md)
4. Review all diagrams in [DOCUMENTATION_INDEX](DOCUMENTATION_INDEX.md)
5. Read API reference and testing documentation

### For System Administrators

1. Study [DEPLOYMENT](DEPLOYMENT.md) guide
2. Review [DOCKER_TEST_RESULTS](DOCKER_TEST_RESULTS.md)
3. Set up [TELEGRAM_SETUP](TELEGRAM_SETUP.md) for alerts
4. Configure [DASHBOARD](DASHBOARD.md) with authentication
5. Implement monitoring and health checks

## 📊 System Status

Current status indicators:

- ✅ **Core System**: Production-ready
- ✅ **Cost Calculator**: Validated against real trades
- ✅ **Risk Engine**: 7-checkpoint validation
- ✅ **Broker Integration**: Zerodha + Groww
- ✅ **Dashboard**: Real-time WebSocket updates
- ✅ **Documentation**: 22 diagrams, 1600+ lines

## 🎯 Next Steps

Ready to get started?

1. **[Quick Start Guide](QUICKSTART.md)** - Install and run in 10 minutes
2. **[Broker Setup](GROWW_SETUP.md)** - Connect to Groww or Zerodha
3. **[Deploy Dashboard](DASHBOARD.md)** - Monitor your trades in real-time

---

**Welcome to intelligent algorithmic trading. Welcome to TradiqAI.** 🤖📈

*Last Updated: February 23, 2026*
