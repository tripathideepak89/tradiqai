#!/bin/bash
# Production startup script for TradiqAI Dashboard

set -e

echo "🚀 Starting TradiqAI Dashboard in production mode..."

# Set production environment
export ENV=production
export DEBUG=false

# Get port from environment or default to 8080
PORT=${PORT:-8080}

echo "📊 Dashboard will be available on port $PORT"
echo "🔒 Running in production mode (DEBUG=false)"

# Run database migrations if needed
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "🔄 Running database migrations..."
    alembic upgrade head
fi

# Start the application
echo "✅ Starting Uvicorn server..."
exec uvicorn dashboard:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 2 \
    --log-level info \
    --access-log \
    --forwarded-allow-ips='*'
