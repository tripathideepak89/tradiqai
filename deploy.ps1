# AutoTrade AI - Windows Production Deployment Script

$ErrorActionPreference = "Stop"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "AutoTrade AI - Production Deployment" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if .env file exists
if (-not (Test-Path .env)) {
    Write-Host "Error: .env file not found!" -ForegroundColor Red
    Write-Host "Please create .env file with your configuration."
    Write-Host "You can copy from .env.example: Copy-Item .env.example .env"
    exit 1
}

Write-Host "[OK] .env file found" -ForegroundColor Green

# Check if Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker is not installed!" -ForegroundColor Red
    Write-Host "Please install Docker Desktop: https://docs.docker.com/desktop/install/windows-install/"
    exit 1
}

Write-Host "[OK] Docker is installed" -ForegroundColor Green

# Check if Docker Compose is available
if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Docker Compose is not installed!" -ForegroundColor Red
    Write-Host "Please install Docker Compose or use Docker Desktop which includes it."
    exit 1
}

Write-Host "[OK] Docker Compose is installed" -ForegroundColor Green

# Create necessary directories
Write-Host ""
Write-Host "Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path logs | Out-Null
New-Item -ItemType Directory -Force -Path data | Out-Null
New-Item -ItemType Directory -Force -Path monitoring | Out-Null

# Stop existing containers
Write-Host ""
Write-Host "Stopping existing containers..." -ForegroundColor Yellow
docker-compose down

# Build and start containers
Write-Host ""
Write-Host "Building Docker images..." -ForegroundColor Yellow
docker-compose build --no-cache

Write-Host ""
Write-Host "Starting services..." -ForegroundColor Yellow
docker-compose up -d

# Wait for services to be healthy
Write-Host ""
Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check service health
Write-Host ""
Write-Host "Checking service health..." -ForegroundColor Yellow

$containers = docker ps --format "{{.Names}}"

if ($containers -match "autotrade-postgres") {
    Write-Host "[OK] PostgreSQL is running" -ForegroundColor Green
} else {
    Write-Host "[FAILED] PostgreSQL failed to start" -ForegroundColor Red
}

if ($containers -match "autotrade-redis") {
    Write-Host "[OK] Redis is running" -ForegroundColor Green
} else {
    Write-Host "[FAILED] Redis failed to start" -ForegroundColor Red
}

if ($containers -match "autotrade-app") {
    Write-Host "[OK] Trading app is running" -ForegroundColor Green
} else {
    Write-Host "[FAILED] Trading app failed to start" -ForegroundColor Red
}

# Show logs
Write-Host ""
Write-Host "Recent logs from trading app:" -ForegroundColor Yellow
Write-Host "======================================" -ForegroundColor Cyan
docker-compose logs --tail=20 app

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services running:" -ForegroundColor Yellow
Write-Host "  - Trading App: Running in background"
Write-Host "  - PostgreSQL: localhost:5432"
Write-Host "  - Redis: localhost:6379"
Write-Host "  - Prometheus: http://localhost:9090 (monitoring)"
Write-Host "  - Grafana: http://localhost:3000 (dashboards)"
Write-Host ""
Write-Host "Management commands:" -ForegroundColor Yellow
Write-Host "  View logs:      docker-compose logs -f app"
Write-Host "  Stop services:  docker-compose down"
Write-Host "  Restart:        docker-compose restart app"
Write-Host "  Shell access:   docker-compose exec app /bin/bash"
Write-Host ""
Write-Host "Database:" -ForegroundColor Yellow
Write-Host "  Connect: docker-compose exec postgres psql -U postgres -d autotrade"
Write-Host ""
