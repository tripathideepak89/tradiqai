# User Authentication System Setup Guide

## Overview

TradiqAI now supports multi-user authentication! Each user can have their own:
- Trading capital and settings
- Isolated trades and performance metrics
- Broker configuration
- Paper trading mode
- Risk parameters

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements_auth.txt
```

This installs:
- `passlib[bcrypt]` - Password hashing
- `python-jose[cryptography]` - JWT token management
- `python-multipart` - Form data support

### 2. Run Database Migration

```bash
python migrate_add_users.py
```

This will:
- Create the `users` table
- Add `user_id` columns to existing tables (trades, daily_metrics, system_logs)
- Create a default admin user
- Link all existing data to the admin user

**Default Admin Credentials:**
- Username: `admin`
- Password: `admin123` (or value from `ADMIN_PASSWORD` env variable)

⚠️ **IMPORTANT:** Change the admin password immediately after first login!

### 3. Configure Environment Variables

Add to your `.env` file:

```bash
# JWT Secret Key (generate a random secure key)
JWT_SECRET_KEY=your-super-secret-key-here-change-this

# Admin Password (used during initial setup)
ADMIN_PASSWORD=your-secure-admin-password
```

To generate a secure JWT secret key:

```python
import secrets
print(secrets.token_urlsafe(32))
```

### 4. Start the Dashboard

```bash
python dashboard.py
```

Visit `http://localhost:8080/login` to log in!

## Usage

### Creating New Users

#### Option 1: Via API

```bash
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "trader1",
    "email": "trader1@example.com",
    "password": "securepass123",
    "full_name": "John Trader"
  }'
```

#### Option 2: Via Web Interface

1. Go to `http://localhost:8080/login`
2. Click "Sign Up"
3. Fill in the form
4. Click "Create Account"

### Logging In

1. Go to `http://localhost:8080/login`
2. Enter username and password
3. Click "Sign In"
4. You'll be redirected to your dashboard

### User-Specific Settings

Each user has their own:

```python
# Capital & Trading Mode
capital: float = 50000.0
paper_trading: bool = True
broker_name: str = "groww"

# Risk Parameters
max_daily_loss: float = 1500.0
max_position_risk: float = 400.0
max_open_positions: int = 2
```

### Updating User Settings

```python
# Via API (requires authentication token)
curl -X PUT http://localhost:8080/api/auth/me/capital \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"capital": 75000.0}'

curl -X PUT http://localhost:8080/api/auth/me/paper-trading \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"paper_trading": false}'
```

## API Endpoints

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Register new user |
| `/api/auth/login` | POST | Login and get JWT token |
| `/api/auth/me` | GET | Get current user info |
| `/api/auth/me/capital` | PUT | Update trading capital |
| `/api/auth/me/paper-trading` | PUT | Toggle paper trading |

### Protected Endpoints

All dashboard API endpoints now require authentication via JWT Bearer token:

```javascript
// JavaScript example
const token = localStorage.getItem('access_token');

fetch('/api/account', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
```

### WebSocket Authentication

WebSocket connections require token as query parameter:

```javascript
const token = localStorage.getItem('access_token');
const ws = new WebSocket(`ws://localhost:8080/ws?token=${token}`);
```

## Security Best Practices

### 1. Change Default Admin Password

```bash
# After first login, update password via API or create new admin user
```

### 2. Use Strong JWT Secret

```bash
# Generate secure key:
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Enable HTTPS in Production

```nginx
# Nginx configuration
server {
    listen 443 ssl;
    server_name dashboard.tradiqai.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
    }
}
```

### 4. Token Expiration

- Access tokens expire after 30 minutes
- Refresh tokens expire after 7 days
- Implement token refresh logic in production

## Database Schema

### User Table

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    capital FLOAT DEFAULT 50000.0,
    paper_trading BOOLEAN DEFAULT TRUE,
    broker_name VARCHAR(50) DEFAULT 'groww',
    broker_config TEXT,
    max_daily_loss FLOAT DEFAULT 1500.0,
    max_position_risk FLOAT DEFAULT 400.0,
    max_open_positions INTEGER DEFAULT 2,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    last_login TIMESTAMP
);
```

### Relationships

```sql
-- Trades are linked to users
ALTER TABLE trades ADD COLUMN user_id INTEGER REFERENCES users(id);

-- Daily metrics are linked to users
ALTER TABLE daily_metrics ADD COLUMN user_id INTEGER REFERENCES users(id);

-- System logs can be user-specific
ALTER TABLE system_logs ADD COLUMN user_id INTEGER REFERENCES users(id);
```

## Troubleshooting

### "User not found" Error

Check if user exists in database:

```sql
SELECT id, username, email, is_active FROM users;
```

### "Authentication failed" on WebSocket

Ensure token is passed correctly:

```javascript
// Check browser console for token
console.log('Token:', localStorage.getItem('access_token'));

// Verify WebSocket URL
const ws = new WebSocket(`ws://localhost:8080/ws?token=${token}`);
```

### Migration Failed

If migration fails halfway:

```bash
# Rollback manually and try again
psql -d autotrade -c "DROP TABLE IF EXISTS users CASCADE;"
python migrate_add_users.py
```

### Token Expired

Implement refresh logic or log in again:

```javascript
// Check token expiration
const token = localStorage.getItem('access_token');
if (!token) {
    window.location.href = '/login';
}
```

## Architecture Changes

### Before (Single User)

```
Dashboard → Database (all trades)
           → Broker API (single account)
```

### After (Multi-User)

```
User 1 → Dashboard → Filter trades by user_id=1 → User 1's data only
User 2 → Dashboard → Filter trades by user_id=2 → User 2's data only
User 3 → Dashboard → Filter trades by user_id=3 → User 3's data only
```

Each user sees only their own:
- Trades
- Performance metrics
- Capital allocation
- Broker settings

## Next Steps

1. ✅ Run migration: `python migrate_add_users.py`
2. ✅ Install dependencies: `pip install -r requirements_auth.txt`
3. ✅ Configure `.env` with JWT_SECRET_KEY
4. ✅ Change admin password after first login
5. ✅ Create user accounts for your traders
6. ✅ Configure individual broker settings per user
7. ✅ Enable HTTPS in production
8. ✅ Implement token refresh (optional)

## Support

For issues or questions:
- GitHub: https://github.com/tripathideepak89/tradiqai/issues
- Documentation: https://docs.tradiqai.com

---

**Welcome to multi-user TradiqAI!** 🎉
