# VelvetEcho Local Testing Guide

This guide will walk you through testing the PatientComet and Lobsterclaws integrations locally with full observability (Prometheus + Jaeger).

---

## Prerequisites

```bash
# Install dependencies
pip install velvetecho prometheus-client opentelemetry-api opentelemetry-sdk opentelemetry-exporter-jaeger structlog alembic

# Or using the project
cd /Users/antoineabdul-massih/Documents/VelvetEcho
pip install -e .
```

---

## Step 1: Start Infrastructure Services

We'll use Docker Compose to run:
- Temporal Server (workflow orchestration)
- PostgreSQL (database)
- Redis (cache & queue)
- Prometheus (metrics)
- Jaeger (tracing)

**File**: `docker-compose.yml` (see below)

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f temporal
```

**Services will be available at**:
- Temporal Web UI: http://localhost:8088
- Prometheus: http://localhost:9090
- Jaeger UI: http://localhost:16686
- PostgreSQL: localhost:5432
- Redis: localhost:6379

---

## Step 2: Test PatientComet Integration

### 2.1 Database Setup

```bash
# Initialize database
python test_scripts/setup_patientcomet_db.py

# Run migrations (if using migrations)
python -c "
from velvetecho.database import MigrationManager
manager = MigrationManager(
    db_url='postgresql://velvetecho:password@localhost/patientcomet',
    migrations_dir='./migrations_patientcomet'
)
# manager.init()  # First time only
# manager.create_migration('initial')
# manager.upgrade()
"
```

### 2.2 Start PatientComet Worker

**Terminal 1**:
```bash
cd /Users/antoineabdul-massih/Documents/VelvetEcho

# Start Temporal worker
python examples/patientcomet_full_integration.py worker
```

**Expected output**:
```
============================================================
PatientComet Worker Starting
============================================================
Task Queue: patientcomet
Workers: 8
Max Concurrent: 50
============================================================
Worker started, waiting for workflows...
```

### 2.3 Start PatientComet API

**Terminal 2**:
```bash
cd /Users/antoineabdul-massih/Documents/VelvetEcho

# Start FastAPI server
python examples/patientcomet_full_integration.py api
```

**Expected output**:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:9800
```

### 2.4 Test PatientComet Workflows

**Terminal 3** (API calls):

```bash
# 1. Create a workspace
curl -X POST http://localhost:9800/api/workspaces \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Project",
    "path": "/path/to/project",
    "description": "Test workspace for integration",
    "language": "python",
    "framework": "fastapi"
  }'

# Save workspace ID from response
WORKSPACE_ID="<uuid-from-response>"

# 2. Start analysis
curl -X POST "http://localhost:9800/api/workspaces/${WORKSPACE_ID}/analyze?profile=quick" \
  -H "Content-Type: application/json"

# Save run ID from response
RUN_ID="<uuid-from-response>"

# 3. Check analysis status
curl http://localhost:9800/api/runs/${RUN_ID}

# 4. List all runs
curl http://localhost:9800/api/runs?limit=10

# 5. Get workspace details
curl http://localhost:9800/api/workspaces/${WORKSPACE_ID}
```

**What you'll see**:
1. Worker Terminal: Analyzers executing in parallel (Phase 1: symbols, imports, types)
2. API Terminal: HTTP requests being processed
3. Temporal UI (http://localhost:8088): Workflow execution DAG
4. Metrics (http://localhost:9090): Workflow duration, activity calls

---

## Step 3: Test Lobsterclaws Integration

### 3.1 Database Setup

```bash
# Initialize database
python test_scripts/setup_lobsterclaws_db.py
```

### 3.2 Start Lobsterclaws Worker

**Terminal 4**:
```bash
cd /Users/antoineabdul-massih/Documents/VelvetEcho

# Start Temporal worker
python examples/lobsterclaws_full_integration.py worker
```

**Expected output**:
```
============================================================
Lobsterclaws Worker Starting
============================================================
Task Queue: lobsterclaws
Workers: 4
RPC Services:
  - Urchinspike: http://localhost:8003
============================================================
Worker started, waiting for workflows...
```

### 3.3 Start Lobsterclaws API

**Terminal 5**:
```bash
cd /Users/antoineabdul-massih/Documents/VelvetEcho

# Start FastAPI server
python examples/lobsterclaws_full_integration.py api
```

**Expected output**:
```
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:9720
```

### 3.4 Test Lobsterclaws Workflows

**Terminal 6** (API calls):

```bash
# 1. Create an agent definition
curl -X POST http://localhost:9720/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test_code_analyst",
    "name": "Test Code Analyst",
    "description": "Analyzes code for testing",
    "category": "code_analysis",
    "model": "claude-sonnet-4.5",
    "tools": ["read_file", "write_file", "execute_command"],
    "system_prompt": "You are a helpful code analyst."
  }'

# Save agent definition ID from response
AGENT_ID="<uuid-from-response>"

# 2. Start agent session
curl -X POST "http://localhost:9720/api/sessions/start?agent_id=${AGENT_ID}&session_name=Test%20Session" \
  -H "Content-Type: application/json" \
  -d '{}'

# Save session ID from response
SESSION_ID="<uuid-from-response>"

# 3. Send message to agent
curl -X POST "http://localhost:9720/api/sessions/${SESSION_ID}/message?message=Analyze%20this%20code" \
  -H "Content-Type: application/json"

# 4. Get session status
curl http://localhost:9720/api/sessions/${SESSION_ID}

# 5. Close session
curl -X POST http://localhost:9720/api/sessions/${SESSION_ID}/close \
  -H "Content-Type: application/json"

# 6. List all agents
curl http://localhost:9720/api/agents

# 7. List all sessions
curl http://localhost:9720/api/sessions
```

**What you'll see**:
1. Worker Terminal: Agent messages being processed, tool calls to Urchinspike
2. API Terminal: HTTP requests and WebSocket connections
3. Temporal UI: Session workflow with signals
4. Metrics: RPC calls, activity duration

---

## Step 4: Observability Dashboards

### 4.1 Prometheus Metrics

**URL**: http://localhost:9090

**Queries to try**:

```promql
# Workflow execution rate
rate(velvetecho_workflow_executions_total[5m])

# Average workflow duration
rate(velvetecho_workflow_duration_seconds_sum[5m]) / rate(velvetecho_workflow_duration_seconds_count[5m])

# Activity call rate by status
rate(velvetecho_activity_calls_total[5m]) by (status)

# Cache hit rate
velvetecho_cache_hit_rate

# Queue depth
velvetecho_queue_depth

# RPC call duration by service
histogram_quantile(0.95, rate(velvetecho_rpc_duration_seconds_bucket[5m])) by (service)

# Database connection pool size
velvetecho_db_connection_pool_size

# Circuit breaker state (0=closed, 1=open, 2=half_open)
velvetecho_circuit_breaker_state
```

### 4.2 Jaeger Tracing

**URL**: http://localhost:16686

**How to use**:
1. Select service: `velvetecho` (or `patientcomet`, `lobsterclaws`)
2. Click "Find Traces"
3. Click on a trace to see:
   - Workflow execution span
   - Activity spans
   - RPC call spans
   - Database query spans
4. See distributed tracing across services

**What you'll see**:
- Full workflow execution timeline
- Activity execution with dependencies
- RPC calls to Urchinspike
- Database queries with timing
- Error traces with exception details

### 4.3 Structured Logs

**View logs**:
```bash
# PatientComet logs
tail -f patientcomet.log | jq .

# Lobsterclaws logs
tail -f lobsterclaws.log | jq .
```

**Example log entry** (JSON):
```json
{
  "timestamp": "2026-02-26T10:30:45.123456Z",
  "level": "info",
  "event": "workflow_started",
  "workflow_id": "abc-123",
  "workflow_name": "patientcomet_analysis_workflow",
  "service": "patientcomet",
  "func_name": "patientcomet_analysis_workflow",
  "lineno": 123
}
```

---

## Step 5: Test Scenarios

### Scenario 1: PatientComet Analysis Pipeline

**Goal**: Analyze a codebase with 111 analyzers

```bash
# 1. Create workspace
WORKSPACE_ID=$(curl -s -X POST http://localhost:9800/api/workspaces \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Project",
    "path": "/path/to/project",
    "language": "python",
    "framework": "fastapi"
  }' | jq -r '.data.id')

echo "Created workspace: $WORKSPACE_ID"

# 2. Start analysis
RUN_ID=$(curl -s -X POST "http://localhost:9800/api/workspaces/${WORKSPACE_ID}/analyze?profile=quick" \
  -H "Content-Type: application/json" | jq -r '.data.id')

echo "Started analysis: $RUN_ID"

# 3. Monitor progress (poll every 5 seconds)
while true; do
  STATUS=$(curl -s http://localhost:9800/api/runs/${RUN_ID} | jq -r '.data.status')
  COMPLETED=$(curl -s http://localhost:9800/api/runs/${RUN_ID} | jq -r '.data.completed_analyzers')
  TOTAL=$(curl -s http://localhost:9800/api/runs/${RUN_ID} | jq -r '.data.total_analyzers')

  echo "Status: $STATUS | Progress: $COMPLETED/$TOTAL"

  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi

  sleep 5
done

# 4. Get final results
curl -s http://localhost:9800/api/runs/${RUN_ID} | jq .
```

**Expected behavior**:
1. ✅ Workspace created in database
2. ✅ Analysis run created (status: PENDING)
3. ✅ Temporal workflow started
4. ✅ Phase 1 analyzers execute in parallel (symbols, imports, types)
5. ✅ Phase 2 analyzers execute (calls, data_flow) - wait for Phase 1
6. ✅ Phase 3+ continue based on dependencies
7. ✅ Status updates to RUNNING → COMPLETED
8. ✅ Results stored in database

**Observability**:
- Prometheus: `velvetecho_workflow_duration_seconds{workflow_name="patientcomet_analysis_workflow"}`
- Jaeger: Search for "patientcomet_analysis_workflow" trace
- Logs: `grep "workflow_started" patientcomet.log`

---

### Scenario 2: Lobsterclaws Agent Session

**Goal**: Long-running agent session with multiple messages

```bash
# 1. Create agent
AGENT_ID=$(curl -s -X POST http://localhost:9720/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "code_analyst_001",
    "name": "Code Analyst",
    "description": "Analyzes code",
    "category": "code_analysis",
    "model": "claude-sonnet-4.5",
    "tools": ["read_file", "write_file"]
  }' | jq -r '.data.id')

echo "Created agent: $AGENT_ID"

# 2. Start session
SESSION_ID=$(curl -s -X POST "http://localhost:9720/api/sessions/start?agent_id=${AGENT_ID}&session_name=Code%20Review" \
  -H "Content-Type: application/json" \
  -d '{}' | jq -r '.data.id')

echo "Started session: $SESSION_ID"

# 3. Send message 1
curl -X POST "http://localhost:9720/api/sessions/${SESSION_ID}/message?message=Read%20the%20main%20file" \
  -H "Content-Type: application/json"

sleep 2

# 4. Send message 2
curl -X POST "http://localhost:9720/api/sessions/${SESSION_ID}/message?message=Write%20a%20summary" \
  -H "Content-Type: application/json"

sleep 2

# 5. Check session status
curl -s http://localhost:9720/api/sessions/${SESSION_ID} | jq .

# 6. Close session
curl -X POST http://localhost:9720/api/sessions/${SESSION_ID}/close \
  -H "Content-Type: application/json"
```

**Expected behavior**:
1. ✅ Agent definition created
2. ✅ Session created (status: ACTIVE)
3. ✅ Temporal SessionWorkflow started
4. ✅ Message 1 sent via Temporal signal
5. ✅ Worker processes message, calls tools via RPC to Urchinspike
6. ✅ Message 2 sent and processed
7. ✅ Session closed (status: COMPLETED)

**Observability**:
- Prometheus: `velvetecho_rpc_calls_total{service="urchinspike"}`
- Jaeger: Search for "agent_session_workflow" trace
- Logs: `grep "rpc_call" lobsterclaws.log`

---

### Scenario 3: Error Handling & Circuit Breaker

**Goal**: Trigger circuit breaker with failed RPC calls

```bash
# 1. Stop Urchinspike (simulate service down)
# (No Urchinspike service running)

# 2. Start session
AGENT_ID="<existing-agent-id>"
SESSION_ID=$(curl -s -X POST "http://localhost:9720/api/sessions/start?agent_id=${AGENT_ID}&session_name=Error%20Test" \
  -H "Content-Type: application/json" \
  -d '{}' | jq -r '.data.id')

# 3. Send message that requires tool (will fail)
for i in {1..6}; do
  curl -X POST "http://localhost:9720/api/sessions/${SESSION_ID}/message?message=Read%20file%20${i}" \
    -H "Content-Type: application/json"
  sleep 1
done

# 4. Check circuit breaker state in Prometheus
# Query: velvetecho_circuit_breaker_state{name="rpc_urchinspike"}
# Expected: 1 (OPEN) after 5 failures
```

**Expected behavior**:
1. ✅ First 5 RPC calls fail
2. ✅ Circuit breaker opens after threshold (5 failures)
3. ✅ Subsequent calls fail immediately (circuit open)
4. ✅ After timeout (60s), circuit goes to HALF_OPEN
5. ✅ One test call allowed
6. ✅ If successful, circuit closes; if fails, stays open

**Observability**:
- Prometheus: `velvetecho_circuit_breaker_state` (0=closed, 1=open, 2=half_open)
- Prometheus: `velvetecho_circuit_breaker_failures_total`
- Jaeger: See failed RPC spans with error details
- Logs: `grep "circuit_breaker" lobsterclaws.log`

---

## Step 6: Cleanup

```bash
# Stop services
docker-compose down

# Remove volumes (careful - deletes data!)
docker-compose down -v

# Stop workers (Ctrl+C in terminals)

# Stop API servers (Ctrl+C in terminals)
```

---

## Troubleshooting

### Issue: Temporal connection error

**Error**: `Could not connect to Temporal server at localhost:7233`

**Solution**:
```bash
# Check if Temporal is running
docker-compose ps temporal

# View Temporal logs
docker-compose logs temporal

# Restart Temporal
docker-compose restart temporal
```

---

### Issue: Database connection error

**Error**: `Connection refused to localhost:5432`

**Solution**:
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres

# Test connection
psql -h localhost -U velvetecho -d patientcomet
```

---

### Issue: Prometheus not showing metrics

**Error**: No metrics in Prometheus UI

**Solution**:
```bash
# 1. Check if metrics endpoint is working
curl http://localhost:9800/metrics  # PatientComet
curl http://localhost:9720/metrics  # Lobsterclaws

# 2. Check Prometheus config
docker-compose exec prometheus cat /etc/prometheus/prometheus.yml

# 3. Check Prometheus targets (should show "UP")
# Visit: http://localhost:9090/targets

# 4. If targets are DOWN, check network
docker-compose exec prometheus ping host.docker.internal
```

---

### Issue: Jaeger not showing traces

**Error**: No traces in Jaeger UI

**Solution**:
```bash
# 1. Check if tracing is enabled in code
# In your workflow/activity:
from velvetecho.observability import init_tracing
tracing = init_tracing(service_name="patientcomet", enabled=True)

# 2. Check Jaeger is running
docker-compose ps jaeger

# 3. Check Jaeger agent port
docker-compose logs jaeger | grep "agent listening"

# 4. Test tracing manually
python -c "
from velvetecho.observability import init_tracing
tracing = init_tracing(service_name='test')
with tracing.trace('test_span'):
    print('traced')
"
```

---

## Next Steps

After successful local testing:
1. ✅ Verify all workflows execute correctly
2. ✅ Check metrics in Prometheus
3. ✅ Verify traces in Jaeger
4. ✅ Review structured logs
5. ➡️ Deploy to staging environment
6. ➡️ Add security layer (auth, encryption)
7. ➡️ Performance testing

---

## Key Metrics to Monitor

| Metric | Query | Target |
|--------|-------|--------|
| Workflow success rate | `rate(velvetecho_workflow_executions_total{status="success"}[5m]) / rate(velvetecho_workflow_executions_total[5m])` | >99% |
| P95 workflow duration | `histogram_quantile(0.95, rate(velvetecho_workflow_duration_seconds_bucket[5m]))` | <60s |
| Activity retry rate | `rate(velvetecho_activity_retries_total[5m]) / rate(velvetecho_activity_calls_total[5m])` | <1% |
| Cache hit rate | `velvetecho_cache_hit_rate` | >80% |
| RPC error rate | `rate(velvetecho_rpc_calls_total{status="error"}[5m]) / rate(velvetecho_rpc_calls_total[5m])` | <0.1% |
| Queue depth | `velvetecho_queue_depth` | <100 |

---

## Summary

This testing guide covers:
- ✅ Infrastructure setup (Temporal, PostgreSQL, Redis, Prometheus, Jaeger)
- ✅ PatientComet integration testing (DAG workflow, 111 analyzers)
- ✅ Lobsterclaws integration testing (SessionWorkflow, RPC)
- ✅ Observability verification (metrics, traces, logs)
- ✅ Error handling & circuit breaker testing
- ✅ Troubleshooting common issues

**You can now test the full stack locally before deploying!**
