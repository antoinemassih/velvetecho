#!/bin/bash
# Test PatientComet workflow end-to-end

set -e

echo "========================================"
echo "PatientComet Workflow Test"
echo "========================================"
echo

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}1. Creating workspace...${NC}"
WORKSPACE_RESPONSE=$(curl -s -X POST http://localhost:9800/api/workspaces \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Project",
    "path": "/path/to/test/project",
    "description": "Test workspace for integration testing",
    "language": "python",
    "framework": "fastapi"
  }')

WORKSPACE_ID=$(echo $WORKSPACE_RESPONSE | jq -r '.data.id')
echo -e "${GREEN}✓ Workspace created: $WORKSPACE_ID${NC}"
echo

echo -e "${BLUE}2. Starting analysis (profile: quick)...${NC}"
ANALYSIS_RESPONSE=$(curl -s -X POST "http://localhost:9800/api/workspaces/${WORKSPACE_ID}/analyze?profile=quick" \
  -H "Content-Type: application/json")

RUN_ID=$(echo $ANALYSIS_RESPONSE | jq -r '.data.id')
WORKFLOW_ID=$(echo $ANALYSIS_RESPONSE | jq -r '.data.workflow_id')
echo -e "${GREEN}✓ Analysis started${NC}"
echo "   Run ID: $RUN_ID"
echo "   Workflow ID: $WORKFLOW_ID"
echo

echo -e "${BLUE}3. Monitoring progress...${NC}"
while true; do
  STATUS_RESPONSE=$(curl -s http://localhost:9800/api/runs/${RUN_ID})
  STATUS=$(echo $STATUS_RESPONSE | jq -r '.data.status')
  COMPLETED=$(echo $STATUS_RESPONSE | jq -r '.data.completed_analyzers')
  TOTAL=$(echo $STATUS_RESPONSE | jq -r '.data.total_analyzers')

  echo "   Status: $STATUS | Progress: $COMPLETED/$TOTAL"

  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi

  sleep 3
done

echo

if [ "$STATUS" = "completed" ]; then
  echo -e "${GREEN}✓ Analysis completed successfully!${NC}"
  echo
  echo -e "${BLUE}4. Checking results...${NC}"
  curl -s http://localhost:9800/api/runs/${RUN_ID} | jq .
  echo
  echo -e "${GREEN}✓ Test passed!${NC}"
  echo
  echo "Next steps:"
  echo "1. View workflow in Temporal UI: http://localhost:8088"
  echo "2. View metrics in Prometheus: http://localhost:9090"
  echo "3. View traces in Jaeger: http://localhost:16686"
else
  echo -e "\033[0;31m✗ Analysis failed${NC}"
  echo
  echo "Error details:"
  curl -s http://localhost:9800/api/runs/${RUN_ID} | jq .
  exit 1
fi
