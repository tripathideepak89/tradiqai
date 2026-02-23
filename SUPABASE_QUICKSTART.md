# 🚀 TradiqAI + Supabase Integration

## What Changed?

TradiqAI now uses **Supabase** instead of local PostgreSQL! This means:

✅ **No local database setup needed** - Everything runs in the cloud  
✅ **Automatic authentication** - Built-in user management with JWT  
✅ **Automatic backups** - Your data is safe and recoverable  
✅ **Free tier** - 500MB database, unlimited API requests  
✅ **Row Level Security** - Each user automatically sees only their data  
✅ **Real-time updates** - WebSocket support built-in  

## Quick Start (3 Steps)

### Step 1: Get Supabase Credentials

Visit your Supabase project:
👉 **https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo**

#### 1.1 Get API Keys
1. Click **Settings** (gear icon) in left sidebar
2. Click **API**
3. Copy these keys:
   - **Project URL**: `https://lmpajbaylwrlqtcqmwoo.supabase.co`
   - **anon public** key (under Project API keys)
   - **service_role** key (under Project API keys) ⚠️ Keep secret!

#### 1.2 Get Database Password
1. Click **Settings** → **Database**
2. Scroll to **Connection string**
3. Click **URI** tab
4. Copy the password from the connection string
   - Or reset it if you forgot: Click **Reset Database Password**

### Step 2: Update `.env` File

Open your `.env` file and update these lines:

```bash
# Supabase Configuration
SUPABASE_URL=https://lmpajbaylwrlqtcqmwoo.supabase.co
SUPABASE_ANON_KEY=your_anon_key_from_step_1
SUPABASE_SERVICE_KEY=your_service_role_key_from_step_1
SUPABASE_DB_PASSWORD=your_database_password

# Update Database URL
DATABASE_URL=postgresql://postgres.lmpajbaylwrlqtcqmwoo:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
```

Replace `YOUR_PASSWORD` with your actual database password.

### Step 3: Run SQL Migration

1. Go to **SQL Editor** in Supabase:
   👉 https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo/sql
   
2. Click **New query**

3. Copy all content from `supabase_migration.sql` file

4. Paste into SQL Editor

5. Click **Run** or press `Ctrl+Enter`

6. You should see: ✅ TradiqAI database schema created successfully!

### Step 4: Install & Test

```powershell
# Install Supabase dependencies
pip install -r requirements_supabase.txt

# Test the connection
python test_supabase.py

# Start the dashboard
python dashboard.py
```

### Step 5: Access Your Dashboard

1. Open browser: http://localhost:8080/login
2. Create your account
3. Start trading!

## What Tables Are Created?

The SQL migration creates these tables:

### 1. **users** - User profiles and settings
- Authentication info (linked to Supabase Auth)
- Trading capital and settings
- Risk parameters
- Broker configuration

### 2. **trades** - All your trading history
- Entry/exit prices and timestamps
- P&L calculation
- Position status
- Strategy info

### 3. **daily_metrics** - Daily performance
- Total trades
- Win rate
- Daily P&L
- Max drawdown

### 4. **system_logs** - Application logs
- Info/warning/error logs
- Module and function tracking
- Debugging info

## Row Level Security (RLS)

Each user **automatically** sees only their own data:

```sql
-- Users can only see their own trades
SELECT * FROM trades;  -- Returns only YOUR trades

-- Users can only update their own profile
UPDATE users SET capital = 60000 WHERE id = auth.uid();  -- Works!
UPDATE users SET capital = 60000 WHERE id = 'other-user-id';  -- Fails!
```

This is handled automatically by Supabase - you don't need to filter by user_id in your queries!

## Benefits Over Local Database

| Feature | Local PostgreSQL | Supabase |
|---------|-----------------|----------|
| Setup Time | 30+ minutes | 5 minutes |
| Requires Installation | Yes (PostgreSQL, Docker) | No |
| Automatic Backups | Manual | Automatic |
| Authentication | Custom JWT | Built-in |
| Data Security | Manual RLS | Automatic RLS |
| Scalability | Limited by hardware | Unlimited |
| Cost | VPS/Server costs | Free tier (500MB) |
| Monitoring | Manual | Built-in dashboard |

## Architecture

### Before (Local)
```
┌─────────────┐
│  TradiqAI   │
│  Dashboard  │
└──────┬──────┘
       │
       v
┌─────────────┐
│ PostgreSQL  │
│  (Local)    │
└─────────────┘
```

### After (Supabase)
```
┌─────────────┐
│  TradiqAI   │
│  Dashboard  │
└──────┬──────┘
       │
       v
┌─────────────────────────┐
│     Supabase Cloud      │
├─────────────────────────┤
│  • PostgreSQL Database  │
│  • Authentication       │
│  • Real-time Engine     │
│  • Storage              │
│  • Auto Backups         │
└─────────────────────────┘
```

## Files Created

1. **supabase_config.py** - Supabase client configuration
2. **supabase_auth.py** - Authentication with Supabase Auth
3. **supabase_migration.sql** - Database schema
4. **requirements_supabase.txt** - Python dependencies
5. **test_supabase.py** - Connection testing script
6. **SUPABASE_SETUP.md** - Detailed documentation

## Troubleshooting

### ❌ Connection Error

```
Error: Could not connect to Supabase
```

**Fix:**
1. Check `SUPABASE_URL` in `.env` is correct
2. Check `SUPABASE_ANON_KEY` is correct
3. Verify internet connection
4. Check Supabase project is active (not paused)

### ❌ Authentication Failed

```
Error: Invalid credentials
```

**Fix:**
1. Make sure you ran the SQL migration
2. Check email/password are correct
3. Verify user was created successfully
4. Check Supabase Auth is enabled (Settings → Authentication)

### ❌ Database Error

```
Error: relation "users" does not exist
```

**Fix:**
1. Run the SQL migration in Supabase SQL Editor
2. Make sure migration completed without errors
3. Refresh your database schema

### ❌ Rate Limiting

Supabase free tier limits:
- 10,000 rows read/sec
- 200 rows written/sec
- 2GB database size

**Fix:**
- Upgrade to Pro plan ($25/month)
- Optimize queries
- Add database indexes

## Need Help?

1. **Supabase Docs**: https://supabase.com/docs
2. **Your Project Dashboard**: https://supabase.com/dashboard/project/lmpajbaylwrlqtcqmwoo
3. **Supabase Discord**: https://discord.supabase.com
4. **TradiqAI Issues**: https://github.com/tripathideepak89/tradiqai/issues

## Advanced: Using Supabase Realtime

Want live updates? Use Supabase Realtime:

```python
from supabase_config import get_supabase_client

supabase = get_supabase_client()

# Subscribe to trades table changes
def on_trade_insert(payload):
    print(f"New trade: {payload}")

supabase.table('trades').on('INSERT', on_trade_insert).subscribe()
```

## Security Best Practices

✅ **DO:**
- Keep `SUPABASE_SERVICE_KEY` secret (never commit to git)
- Use `SUPABASE_ANON_KEY` in frontend
- Enable Row Level Security on all tables
- Use environment variables for credentials

❌ **DON'T:**
- Share service role key publicly
- Disable RLS without understanding implications
- Use service key in frontend code
- Store passwords in plain text

## What's Next?

1. ✅ Get Supabase credentials
2. ✅ Update `.env` file
3. ✅ Run SQL migration
4. ✅ Install dependencies
5. ✅ Test connection
6. ✅ Start dashboard
7. ✅ Create your account
8. ✅ Start trading!

---

**🎉 You're now running TradiqAI on Supabase! Happy Trading! 📈**
