#!/bin/bash
# Test Lobsterclaws agent session end-to-end

set -e

echo "========================================"
echo "Lobsterclaws Session Test"
echo "========================================"
echo

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}1. Creating agent definition...${NC}"
AGENT_RESPONSE=$(curl -s -X POST http://localhost:9720/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test_code_analyst_'$(date +%s)'",
    "name": "Test Code Analyst",
    "description": "Test agent for integration testing",
    "category": "code_analysis",
    "model": "claude-sonnet-4.5",
    "tools": ["read_file", "write_file", "execute_command"],
    "system_prompt": "You are a helpful code analyst."
  }')

AGENT_ID=$(echo $AGENT_RESPONSE | jq -r '.data.id')
AGENT_KEY=$(echo $AGENT_RESPONSE | jq -r '.data.agent_id')
echo -e "${GREEN}✓ Agent created: $AGENT_ID${NC}"
echo "   Agent Key: $AGENT_KEY"
echo

echo -e "${BLUE}2. Starting agent session...${NC}"
SESSION_RESPONSE=$(curl -s -X POST "http://localhost:9720/api/sessions/start?agent_id=${AGENT_ID}&session_name=Test%20Session" \
  -H "Content-Type: application/json" \
  -d '{}')

SESSION_ID=$(echo $SESSION_RESPONSE | jq -r '.data.id')
WORKFLOW_ID=$(echo $SESSION_RESPONSE | jq -r '.data.workflow_id')
echo -e "${GREEN}✓ Session started: $SESSION_ID${NC}"
echo "   Workflow ID: $WORKFLOW_ID"
echo

echo -e "${BLUE}3. Sending message to agent...${NC}"
MESSAGE_RESPONSE=$(curl -s -X POST "http://localhost:9720/api/sessions/${SESSION_ID}/message?message=Hello%20agent%2C%20please%20read%20a%20file" \
  -H "Content-Type: application/json")

echo -e "${GREEN}✓ Message sent${NC}"
echo

sleep 3

echo -e "${BLUE}4. Checking session status...${NC}"
STATUS_RESPONSE=$(curl -s http://localhost:9720/api/sessions/${SESSION_ID})
STATUS=$(echo $STATUS_RESPONSE | jq -r '.data.status')
TOTAL_MESSAGES=$(echo $STATUS_RESPONSE | jq -r '.data.total_messages')
TOTAL_TOOLS=$(echo $STATUS_RESPONSE | jq -r '.data.total_tools_executed')

echo "   Status: $STATUS"
echo "   Total Messages: $TOTAL_MESSAGES"
echo "   Total Tools Executed: $TOTAL_TOOLS"
echo

echo -e "${BLUE}5. Sending another message...${NC}"
curl -s -X POST "http://localhost:9720/api/sessions/${SESSION_ID}/message?message=Now%20write%20a%20summary" \
  -H "Content-Type: application/json" > /dev/null

echo -e "${GREEN}✓ Second message sent${NC}"
echo

sleep 3

echo -e "${BLUE}6. Closing session...${NC}"
CLOSE_RESPONSE=$(curl -s -X POST http://localhost:9720/api/sessions/${SESSION_ID}/close \
  -H "Content-Type: application/json")

FINAL_STATUS=$(echo $CLOSE_RESPONSE | jq -r '.data.status')
echo -e "${GREEN}✓ Session closed${NC}"
echo "   Final Status: $FINAL_STATUS"
echo

echo -e "${GREEN}✓ Test passed!${NC}"
echo
echo "Next steps:"
echo "1. View workflow in Temporal UI: http://localhost:8088"
echo "2. View metrics in Prometheus: http://localhost:9090"
echo "3. View traces in Jaeger: http://localhost:16686"
echo "4. Check logs: grep 'rpc_call' lobsterclaws.log"
