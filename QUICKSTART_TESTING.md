# VelvetEcho Quick Start - Local Testing

Get the full VelvetEcho stack running locally in 5 minutes.

---

## Prerequisites

```bash
# 1. Docker Desktop installed and running
docker --version

# 2. Python 3.9+ with pip
python --version

# 3. jq for JSON parsing (optional but recommended)
brew install jq  # macOS
# or: sudo apt-get install jq  # Linux
```

---

## Quick Start (5 Minutes)

### Step 1: Start Infrastructure (1 minute)

```bash
cd /Users/antoineabdul-massih/Documents/VelvetEcho

# Start all services (Temporal, PostgreSQL, Redis, Prometheus, Jaeger)
docker-compose up -d

# Wait for services to be ready (~30 seconds)
sleep 30

# Check status (all should be "Up")
docker-compose ps
```

**Verify services**:
- ✅ Temporal UI: http://localhost:8088
- ✅ Prometheus: http://localhost:9090
- ✅ Jaeger: http://localhost:16686
- ✅ PostgreSQL: `psql -h localhost -U velvetecho -d patientcomet` (password: `password`)
- ✅ Redis: `redis-cli ping` → `PONG`

---

### Step 2: Setup Databases (30 seconds)

```bash
# Setup PatientComet database
cd test_scripts
python setup_patientcomet_db.py
# Enter 'y' to insert test data

# Setup Lobsterclaws database
python setup_lobsterclaws_db.py
# Enter 'y' to insert test data

cd ..
```

---

### Step 3: Test PatientComet Integration (2 minutes)

**Terminal 1** - Start Worker:
```bash
python examples/patientcomet_full_integration.py worker
```

**Terminal 2** - Start API:
```bash
python examples/patientcomet_full_integration.py api
```

**Terminal 3** - Run Test:
```bash
cd test_scripts
./test_patientcomet_workflow.sh
```

**Expected Output**:
```
========================================
PatientComet Workflow Test
========================================

1. Creating workspace...
✓ Workspace created: abc-123-def-456

2. Starting analysis (profile: quick)...
✓ Analysis started
   Run ID: xyz-789-uvw-012
   Workflow ID: analysis-xyz-789

3. Monitoring progress...
   Status: running | Progress: 3/6
   Status: running | Progress: 5/6
   Status: completed | Progress: 6/6

✓ Analysis completed successfully!

✓ Test passed!

Next steps:
1. View workflow in Temporal UI: http://localhost:8088
2. View metrics in Prometheus: http://localhost:9090
3. View traces in Jaeger: http://localhost:16686
```

---

### Step 4: Test Lobsterclaws Integration (2 minutes)

**Terminal 4** - Start Worker:
```bash
python examples/lobsterclaws_full_integration.py worker
```

**Terminal 5** - Start API:
```bash
python examples/lobsterclaws_full_integration.py api
```

**Terminal 6** - Run Test:
```bash
cd test_scripts
./test_lobsterclaws_session.sh
```

**Expected Output**:
```
========================================
Lobsterclaws Session Test
========================================

1. Creating agent definition...
✓ Agent created: abc-123-def-456
   Agent Key: test_code_analyst_1234567890

2. Starting agent session...
✓ Session started: xyz-789-uvw-012
   Workflow ID: session-xyz-789

3. Sending message to agent...
✓ Message sent

4. Checking session status...
   Status: active
   Total Messages: 1
   Total Tools Executed: 1

5. Sending another message...
✓ Second message sent

6. Closing session...
✓ Session closed
   Final Status: completed

✓ Test passed!
```

---

## Observability Dashboards

### Prometheus (Metrics)

**URL**: http://localhost:9090

**Try these queries**:

```promql
# Workflow execution rate
rate(velvetecho_workflow_executions_total[5m])

# P95 workflow duration
histogram_quantile(0.95, rate(velvetecho_workflow_duration_seconds_bucket[5m]))

# Cache hit rate
velvetecho_cache_hit_rate

# RPC calls by service
rate(velvetecho_rpc_calls_total[5m]) by (service, status)
```

---

### Jaeger (Distributed Tracing)

**URL**: http://localhost:16686

1. Select service: `patientcomet` or `lobsterclaws`
2. Click "Find Traces"
3. Click a trace to see:
   - Workflow span
   - Activity spans
   - RPC calls
   - Database queries
   - Timing details

---

### Temporal UI (Workflow Orchestration)

**URL**: http://localhost:8088

1. Click "Workflows" in sidebar
2. See running/completed workflows
3. Click a workflow to see:
   - Execution history
   - Input/output
   - Events timeline
   - Worker assignments

---

## Manual Testing

### PatientComet API

```bash
# Create workspace
curl -X POST http://localhost:9800/api/workspaces \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Project",
    "path": "/path/to/project",
    "language": "python"
  }'

# Start analysis
curl -X POST "http://localhost:9800/api/workspaces/{id}/analyze?profile=quick"

# Check status
curl http://localhost:9800/api/runs/{run_id}

# List workspaces
curl http://localhost:9800/api/workspaces
```

---

### Lobsterclaws API

```bash
# Create agent
curl -X POST http://localhost:9720/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my_agent",
    "name": "My Agent",
    "category": "code_analysis",
    "model": "claude-sonnet-4.5",
    "tools": ["read_file"]
  }'

# Start session
curl -X POST "http://localhost:9720/api/sessions/start?agent_id={id}&session_name=Test"

# Send message
curl -X POST "http://localhost:9720/api/sessions/{session_id}/message?message=Hello"

# Close session
curl -X POST http://localhost:9720/api/sessions/{session_id}/close
```

---

## Metrics Endpoints

Both APIs expose Prometheus metrics:

```bash
# PatientComet metrics
curl http://localhost:9800/metrics

# Lobsterclaws metrics
curl http://localhost:9720/metrics
```

---

## Cleanup

```bash
# Stop all services
docker-compose down

# Remove volumes (deletes data!)
docker-compose down -v

# Stop workers (Ctrl+C in terminals)
# Stop API servers (Ctrl+C in terminals)
```

---

## Troubleshooting

### Services won't start

```bash
# Check Docker
docker ps

# View logs
docker-compose logs temporal
docker-compose logs postgres

# Restart specific service
docker-compose restart temporal
```

---

### Database connection error

```bash
# Test connection
psql -h localhost -U velvetecho -d patientcomet
# Password: password

# If fails, check PostgreSQL is running
docker-compose ps postgres
docker-compose logs postgres
```

---

### Metrics not showing

```bash
# 1. Check metrics endpoint
curl http://localhost:9800/metrics
curl http://localhost:9720/metrics

# 2. Check Prometheus targets (should be "UP")
# Visit: http://localhost:9090/targets

# 3. If DOWN, check network
docker-compose exec prometheus ping host.docker.internal
```

---

### Traces not showing

```bash
# Check Jaeger is running
docker-compose ps jaeger

# Check if tracing is enabled in code
# Should see: [Tracing] Enabled for patientcomet → localhost:6831
```

---

## What's Next?

After successful local testing:

1. ✅ Verify workflows execute correctly
2. ✅ Check metrics in Prometheus
3. ✅ Verify traces in Jaeger
4. ✅ Test error scenarios
5. ➡️ Deploy to staging environment
6. ➡️ Performance testing
7. ➡️ Security layer (if needed)

---

## Summary

You now have:

- ✅ Full VelvetEcho stack running locally
- ✅ PatientComet integration tested
- ✅ Lobsterclaws integration tested
- ✅ Observability dashboards configured
- ✅ Metrics & tracing working

**Time to complete**: ~5 minutes
**Services running**: 6 (Temporal, PostgreSQL, Redis, Prometheus, Jaeger, Grafana)
**APIs running**: 2 (PatientComet, Lobsterclaws)
**Workers running**: 2 (PatientComet, Lobsterclaws)

**Ready for production deployment!** 🚀
