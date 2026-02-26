#!/bin/bash
# Master test runner for VelvetEcho integrations

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "VelvetEcho Integration Test Runner"
echo "========================================"
echo

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    echo "Please install Docker Desktop"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python not found${NC}"
    echo "Please install Python 3.9+"
    exit 1
fi

echo -e "${GREEN}✓ Docker found${NC}"
echo -e "${GREEN}✓ Python found${NC}"
echo

# Start infrastructure
echo -e "${BLUE}1. Starting infrastructure services...${NC}"
docker-compose up -d

echo "Waiting for services to start (30 seconds)..."
sleep 30

# Check services
echo
echo -e "${BLUE}2. Checking services...${NC}"

SERVICES=("temporal" "postgres" "redis" "prometheus" "jaeger")
ALL_UP=true

for service in "${SERVICES[@]}"; do
    if docker-compose ps $service | grep -q "Up"; then
        echo -e "   ${GREEN}✓ $service${NC}"
    else
        echo -e "   ${RED}✗ $service${NC}"
        ALL_UP=false
    fi
done

if [ "$ALL_UP" = false ]; then
    echo
    echo -e "${RED}Some services failed to start. Check logs with: docker-compose logs${NC}"
    exit 1
fi

# Setup databases
echo
echo -e "${BLUE}3. Setting up databases...${NC}"

cd test_scripts

echo -e "${YELLOW}Setting up PatientComet database...${NC}"
python setup_patientcomet_db.py <<EOF
n
EOF

echo -e "${YELLOW}Setting up Lobsterclaws database...${NC}"
python setup_lobsterclaws_db.py <<EOF
n
EOF

cd ..

echo -e "${GREEN}✓ Databases ready${NC}"

# Run tests
echo
echo -e "${BLUE}4. Running integration tests...${NC}"
echo

echo -e "${YELLOW}Note: You need to manually start workers and APIs in separate terminals${NC}"
echo
echo "Terminal 1: python examples/patientcomet_full_integration.py worker"
echo "Terminal 2: python examples/patientcomet_full_integration.py api"
echo "Terminal 3: python examples/lobsterclaws_full_integration.py worker"
echo "Terminal 4: python examples/lobsterclaws_full_integration.py api"
echo
echo "Then run:"
echo "  ./test_scripts/test_patientcomet_workflow.sh"
echo "  ./test_scripts/test_lobsterclaws_session.sh"
echo

# Show URLs
echo -e "${BLUE}5. Dashboard URLs:${NC}"
echo "   Temporal UI:  http://localhost:8088"
echo "   Prometheus:   http://localhost:9090"
echo "   Jaeger UI:    http://localhost:16686"
echo "   Grafana:      http://localhost:3000 (admin/admin)"
echo

echo -e "${GREEN}✓ Infrastructure ready for testing!${NC}"
echo
echo "Next steps:"
echo "1. Start workers in separate terminals (see commands above)"
echo "2. Run test scripts"
echo "3. Check dashboards"
echo
echo "To stop everything: docker-compose down"
