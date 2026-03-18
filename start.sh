#!/bin/bash
# TradiqAI startup — runs trading bot + web dashboard in the same Railway service.
# Trading bot auto-restarts on crash; dashboard stays in foreground for healthchecks.

set -e

# Ensure log directory exists for trading bot file handlers
mkdir -p logs

echo "[START] Launching TradiqAI..."

# Set production environment
export ENV=production
export DEBUG=false

PORT=${PORT:-8000}
echo "[START] Dashboard on port $PORT"

# Run database migrations if needed
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "[START] Running database migrations..."
    alembic upgrade head
fi

# ── Trading bot (background, auto-restart on crash) ──────────────────────────
(
  set +e  # disable errexit in subshell so crashes don't kill the restart loop
  while true; do
    echo "[TRADING BOT] Starting main.py..."
    python3 main.py
    EXIT_CODE=$?
    echo "[TRADING BOT] main.py exited (code $EXIT_CODE). Restarting in 20s..."
    sleep 20
  done
) &

echo "[START] Trading bot started in background (auto-restart enabled)"

# Small delay so bot can initialise DB/broker before dashboard starts serving
sleep 3

# ── Web dashboard (foreground — Railway healthcheck + process lifecycle) ──────
echo "[START] Starting dashboard..."
exec python3 -m uvicorn dashboard:app \
    --host 0.0.0.0 \
    --port $PORT \
    --log-level info \
    --access-log \
    --forwarded-allow-ips='*'
