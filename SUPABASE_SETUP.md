# Supabase Integration Guide for TradiqAI

## Overview

TradiqAI now uses **Supabase** for:
- ✅ **Managed PostgreSQL Database** - No local database setup needed
- ✅ **Built-in Authentication** - User signup, login, JWT tokens
- ✅ **Real-time Subscriptions** - Live data updates
- ✅ **Row Level Security (RLS)** - Automatic data isolation per user
- ✅ **Automatic Backups** - Your data is safe
- ✅ **Free Tier** - 500MB database, unlimited API requests

## Supabase Project

**Project URL:** https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo
**Project Reference:** `lmpajbaylwrlqtcqmwoo`

## Quick Setup

### 1. Get Your Supabase Credentials

Visit your Supabase project dashboard and get:

1. **Project URL**: `https://lmpajbaylwrlqtcqmwoo.supabase.co`
2. **Anon/Public Key**: Settings → API → `anon` `public` key
3. **Service Role Key**: Settings → API → `service_role` key (keep secret!)
4. **Database Password**: Settings → Database → Connection string → Password

### 2. Update `.env` File

Add these to your `.env` file:

```bash
# Supabase Configuration
SUPABASE_URL=https://lmpajbaylwrlqtcqmwoo.supabase.co
SUPABASE_ANON_KEY=your_anon_public_key_here
SUPABASE_SERVICE_KEY=your_service_role_key_here
SUPABASE_DB_PASSWORD=your_database_password

# Update Database URL to use Supabase
# Pooler connection (recommended for applications)
DATABASE_URL=postgresql://postgres.lmpajbaylwrlqtcqmwoo:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres

# Or direct connection (for migrations)
# DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.lmpajbaylwrlqtcqmwoo.supabase.co:5432/postgres
```

### 3. Install Supabase Dependencies

```powershell
pip install -r requirements_supabase.txt
```

This installs:
- `supabase` - Python client for Supabase
- `postgrest-py` - PostgreSQL REST API client

### 4. Create Database Schema in Supabase

Run the SQL migration in Supabase SQL Editor:

1. Go to: https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo/editor
2. Click **SQL Editor** → **New query**
3. Copy and paste the SQL from `supabase_migration.sql` (creating next)
4. Click **Run** or press `Ctrl+Enter`

### 5. Enable Row Level Security (RLS)

Supabase automatically ensures each user sees only their data:

```sql
-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_metrics ENABLE ROW LEVEL SECURITY;

-- Users can only see their own data
CREATE POLICY "Users can view own profile"
  ON users FOR SELECT
  USING (auth.uid() = id::text);

CREATE POLICY "Users can update own profile"
  ON users FOR UPDATE
  USING (auth.uid() = id::text);

-- Trades: Users can only see their own trades
CREATE POLICY "Users can view own trades"
  ON trades FOR SELECT
  USING (auth.uid() = user_id::text);

CREATE POLICY "Users can insert own trades"
  ON trades FOR INSERT
  WITH CHECK (auth.uid() = user_id::text);

-- Daily metrics: Users can only see their own metrics
CREATE POLICY "Users can view own metrics"
  ON daily_metrics FOR SELECT
  USING (auth.uid() = user_id::text);
```

## Architecture Changes

### Before (Local Database)

```
TradiqAI → Local PostgreSQL → Local Storage
         → Custom JWT Auth
         → Manual user management
```

### After (Supabase)

```
TradiqAI → Supabase Auth → JWT Tokens (automatic)
         → Supabase PostgreSQL → Managed Cloud Storage
         → Row Level Security → Data isolation (automatic)
         → Real-time subscriptions → Live updates
```

## Authentication Flow

### 1. Register New User

```python
POST /api/auth/register
{
  "email": "trader@example.com",
  "password": "securepass123",
  "username": "trader1",
  "full_name": "John Trader"
}

# Supabase creates:
# - User in auth.users table (authentication)
# - Profile in public.users table (trading settings)
# - JWT tokens automatically
```

### 2. Login

```python
POST /api/auth/login
{
  "email": "trader@example.com",
  "password": "securepass123"
}

# Returns:
{
  "access_token": "eyJhbG...",  # JWT token
  "refresh_token": "eyJhbG...",  # Refresh token
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "trader@example.com",
    "username": "trader1",
    "capital": 50000.0,
    "paper_trading": true
  }
}
```

### 3. Access Protected Routes

```javascript
// Frontend
const token = localStorage.getItem('access_token');

fetch('/api/account', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

// Backend validates token with Supabase automatically
```

## Database Schema

### Users Table

```sql
CREATE TABLE public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(100),
    capital DECIMAL(15, 2) DEFAULT 50000.00,
    paper_trading BOOLEAN DEFAULT true,
    broker_name VARCHAR(50) DEFAULT 'groww',
    broker_config JSONB,
    max_daily_loss DECIMAL(15, 2) DEFAULT 1500.00,
    max_position_risk DECIMAL(15, 2) DEFAULT 400.00,
    max_open_positions INTEGER DEFAULT 2,
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    last_login TIMESTAMP WITH TIME ZONE
);
```

### Trades Table

```sql
CREATE TABLE public.trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,  -- BUY/SELL
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(15, 2) NOT NULL,
    exit_price DECIMAL(15, 2),
    entry_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    exit_timestamp TIMESTAMP WITH TIME ZONE,
    pnl DECIMAL(15, 2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'OPEN',  -- OPEN/CLOSED
    broker_order_id VARCHAR(100),
    strategy VARCHAR(50),
    risk_reward DECIMAL(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_trades_user_id ON trades(user_id);
CREATE INDEX idx_trades_timestamp ON trades(entry_timestamp);
CREATE INDEX idx_trades_symbol ON trades(symbol);
```

### Daily Metrics Table

```sql
CREATE TABLE public.daily_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_pnl DECIMAL(15, 2) DEFAULT 0,
    win_rate DECIMAL(5, 2) DEFAULT 0,
    max_drawdown DECIMAL(15, 2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, date)
);

CREATE INDEX idx_daily_metrics_user_date ON daily_metrics(user_id, date);
```

## Benefits of Supabase

### 1. **No Database Setup Required**
- No need to install PostgreSQL locally
- No Docker containers needed
- Works on any machine with internet connection

### 2. **Automatic Backups**
- Daily automatic backups
- Point-in-time recovery
- Data always safe

### 3. **Built-in Authentication**
- Industry-standard JWT tokens
- Password hashing handled automatically
- Email verification ready (if enabled)
- Social login ready (Google, GitHub, etc.)

### 4. **Row Level Security (RLS)**
- Users automatically see only their data
- No manual filtering needed in queries
- Secure by default

### 5. **Real-time Subscriptions**
- Listen to database changes in real-time
- Perfect for live dashboard updates
- WebSocket-based

### 6. **Free Tier Generous**
- 500MB database storage
- Unlimited API requests
- 50,000 monthly active users
- 2GB file storage

### 7. **Scalability**
- Scales automatically
- No server management
- Upgrade anytime

## Migration from Local Database

### Option 1: Fresh Start (Recommended)

1. Update `.env` with Supabase credentials
2. Run schema migration in Supabase SQL Editor
3. Start fresh with new users

### Option 2: Migrate Existing Data

```powershell
# Export from SQLite
python export_local_db.py  # Creates trades_export.csv

# Import to Supabase using SQL Editor
COPY trades(user_id, symbol, side, quantity, entry_price, ...)
FROM '/path/to/trades_export.csv'
DELIMITER ','
CSV HEADER;
```

## Testing

### 1. Register a Test User

```powershell
curl -X POST http://localhost:8080/api/auth/register `
  -H "Content-Type: application/json" `
  -d '{
    "email": "test@tradiqai.com",
    "password": "test123456",
    "username": "testuser",
    "full_name": "Test User"
  }'
```

### 2. Login

```powershell
curl -X POST http://localhost:8080/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{
    "email": "test@tradiqai.com",
    "password": "test123456"
  }'
```

### 3. Access Protected Route

```powershell
curl -X GET http://localhost:8080/api/auth/me `
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Troubleshooting

### Connection Error

```
Error: Could not connect to Supabase
```

**Solution:**
- Check `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `.env`
- Verify internet connection
- Check Supabase project status

### Authentication Failed

```
Error: Invalid or expired token
```

**Solution:**
- Token expired (60 minutes by default)
- Use refresh token to get new access token
- Re-login if refresh token also expired

### Database Error

```
Error: permission denied for table trades
```

**Solution:**
- Enable RLS policies in Supabase SQL Editor
- Check user is authenticated
- Verify user_id matches auth.uid()

### Rate Limiting

Supabase free tier limits:
- 10,000 rows read per second
- 200 rows written per second

**Solution:**
- Upgrade to Pro plan if needed
- Optimize queries with indexes

## Next Steps

1. ✅ Update `.env` with Supabase credentials
2. ✅ Install dependencies: `pip install -r requirements_supabase.txt`
3. ✅ Run SQL migration in Supabase SQL Editor
4. ✅ Enable Row Level Security policies
5. ✅ Test authentication flow
6. ✅ Start trading!

## Support

- **Supabase Docs**: https://supabase.com/docs
- **Supabase Dashboard**: https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo
- **TradiqAI Issues**: https://github.com/tripathideepak89/tradiqai/issues

---

**🎉 Welcome to Cloud-Based TradiqAI with Supabase!**
