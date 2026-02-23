#!/bin/bash
# AutoTrade AI - Production Deployment Script

set -e  # Exit on error

echo "======================================"
echo "AutoTrade AI - Production Deployment"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please create .env file with your configuration."
    echo "You can copy from .env.example: cp .env.example .env"
    exit 1
fi

echo -e "${GREEN}✓${NC} .env file found"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed!${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker is installed"

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed!${NC}"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker Compose is installed"

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p logs data monitoring

# Stop existing containers
echo ""
echo "Stopping existing containers..."
docker-compose down

# Build and start containers
echo ""
echo "Building Docker images..."
docker-compose build --no-cache

echo ""
echo "Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo ""
echo "Waiting for services to be ready..."
sleep 10

# Check service health
echo ""
echo "Checking service health..."

if docker ps | grep -q autotrade-postgres; then
    echo -e "${GREEN}✓${NC} PostgreSQL is running"
else
    echo -e "${RED}✗${NC} PostgreSQL failed to start"
fi

if docker ps | grep -q autotrade-redis; then
    echo -e "${GREEN}✓${NC} Redis is running"
else
    echo -e "${RED}✗${NC} Redis failed to start"
fi

if docker ps | grep -q autotrade-app; then
    echo -e "${GREEN}✓${NC} Trading app is running"
else
    echo -e "${RED}✗${NC} Trading app failed to start"
fi

# Show logs
echo ""
echo "Recent logs from trading app:"
echo "======================================"
docker-compose logs --tail=20 app

echo ""
echo "======================================"
echo -e "${GREEN}Deployment Complete!${NC}"
echo "======================================"
echo ""
echo "Services running:"
echo "  - Trading App: Running in background"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis: localhost:6379"
echo "  - Prometheus: http://localhost:9090 (monitoring)"
echo "  - Grafana: http://localhost:3000 (dashboards)"
echo ""
echo "Management commands:"
echo "  View logs:      docker-compose logs -f app"
echo "  Stop services:  docker-compose down"
echo "  Restart:        docker-compose restart app"
echo "  Shell access:   docker-compose exec app /bin/bash"
echo ""
echo "Database:"
echo "  Connect: docker-compose exec postgres psql -U postgres -d autotrade"
echo ""
