# VelvetEcho - Monitoring & Operations Guide

**Last Updated**: 2026-03-01
**Version**: 1.0
**For**: PatientComet Operations Team

---

## 🎯 Overview

This guide covers day-to-day operations, monitoring, and troubleshooting for VelvetEcho in production.

---

## 📊 Monitoring Dashboards

### 1. Temporal UI (Primary Dashboard)

**URL**: http://localhost:8088

#### Key Screens

**Workflows List** (`/namespaces/default/workflows`)
- View all workflows
- Filter by status (Running, Completed, Failed)
- Search by ID or type
- Sort by start time

**Workflow Detail** (`/namespaces/default/workflows/{id}`)
- Execution timeline
- Activity results
- Error stack traces
- Retry history
- Event history (full audit log)

#### Useful Filters

```
# Show running workflows
Status: Running

# Show failed workflows in last 24h
Status: Failed
Time Range: Last 24 hours

# Show PatientComet analyses
Workflow Type: PatientCometAnalysisWorkflow

# Find specific workspace
Search: workspace-id-here
```

---

### 2. Prometheus Metrics

**URL**: http://localhost:9090

#### Key Metrics

**Workflow Metrics**:
```promql
# Active workflows
temporal_workflow_execution_total{status="running"}

# Workflow success rate
rate(temporal_workflow_execution_total{status="completed"}[5m])
/
rate(temporal_workflow_execution_total[5m])

# Average workflow duration
rate(temporal_workflow_execution_time_seconds_sum[5m])
/
rate(temporal_workflow_execution_time_seconds_count[5m])
```

**Activity Metrics**:
```promql
# Activity failures
rate(temporal_activity_execution_failed_total[5m])

# Activity timeout rate
rate(temporal_activity_execution_timeout_total[5m])

# Activity retry rate
rate(temporal_activity_execution_retry_total[5m])
```

**Worker Metrics**:
```promql
# Available task slots
temporal_worker_task_slots_available

# Worker poll rate
rate(temporal_worker_poll_total[5m])

# Task latency
temporal_worker_task_latency_seconds
```

---

### 3. Grafana Dashboards

**URL**: http://localhost:3000
**Login**: admin/admin

#### Pre-built Dashboards

**1. Temporal Overview**
- Workflow throughput
- Activity success/failure rates
- Worker utilization
- Queue depth

**2. PatientComet Analysis**
- Analyses running
- Average completion time
- Analyzer failure rate
- Per-analyzer performance

**3. System Resources**
- CPU usage (workers, Temporal server)
- Memory usage
- Disk I/O
- Network traffic

#### Creating Custom Dashboards

1. Login to Grafana
2. Click "+" → "Dashboard"
3. Add Panel
4. Select Prometheus datasource
5. Enter PromQL query
6. Configure visualization
7. Save dashboard

**Example Panel**:
```
Title: PatientComet Analyses (Last Hour)
Query: sum(rate(temporal_workflow_execution_total{workflow_type="PatientCometAnalysisWorkflow"}[1h]))
Visualization: Time series graph
```

---

### 4. Jaeger Tracing

**URL**: http://localhost:16686

#### Use Cases

- End-to-end latency analysis
- Identify slow activities
- Trace dependencies between services
- Debug distributed issues

#### Searching Traces

**Service**: `temporal`
**Operation**: Select workflow or activity
**Tags**: `workflow.id=your-workflow-id`

---

## 🚨 Alerting

### Recommended Alerts

#### Critical Alerts (Page on-call)

**1. High Workflow Failure Rate**
```promql
rate(temporal_workflow_execution_total{status="failed"}[5m]) > 0.1
```
**Threshold**: >10% failure rate
**Action**: Check Temporal UI for errors

**2. Worker Down**
```promql
up{job="temporal-worker"} == 0
```
**Threshold**: Worker not reporting
**Action**: Restart worker, check logs

**3. Temporal Server Down**
```promql
up{job="temporal"} == 0
```
**Threshold**: Server unreachable
**Action**: Restart Temporal, check PostgreSQL

**4. Database Connection Errors**
```promql
rate(temporal_persistence_errors_total[5m]) > 1
```
**Threshold**: >1 error/sec
**Action**: Check PostgreSQL health

#### Warning Alerts (Notify team)

**5. High Activity Timeout Rate**
```promql
rate(temporal_activity_execution_timeout_total[10m]) > 0.05
```
**Threshold**: >5% timeout rate
**Action**: Review activity timeouts, increase if needed

**6. Queue Depth Growing**
```promql
temporal_workflow_task_queue_depth > 100
```
**Threshold**: >100 tasks queued
**Action**: Add more workers

**7. High Retry Rate**
```promql
rate(temporal_activity_execution_retry_total[5m]) > 10
```
**Threshold**: >10 retries/sec
**Action**: Investigate failing activities

---

## 🔍 Troubleshooting Guide

### Scenario 1: Workflow Stuck

**Symptoms**:
- Workflow shows "Running" for long time
- No recent activity completions

**Diagnosis**:
1. Open Temporal UI → Workflow
2. Check "History" tab
3. Find last completed activity
4. Look for timer or signal

**Possible Causes**:
- ❌ Worker crashed (activity not being executed)
- ❌ Activity stuck in infinite loop
- ❌ Waiting for external signal (if using signals)

**Resolution**:
1. Check worker is running: `docker ps | grep worker`
2. Check worker logs: `docker logs velvetecho-worker`
3. If worker crashed, restart: `docker-compose restart worker`
4. If activity stuck, cancel workflow and investigate code

---

### Scenario 2: High Failure Rate

**Symptoms**:
- Many workflows failing
- Error rate alert firing

**Diagnosis**:
1. Temporal UI → Workflows → Filter: Status=Failed
2. Click failed workflow
3. Check "Stack Trace" tab
4. Look for common error pattern

**Common Causes**:
- ❌ Database connection error (PatientComet DB down)
- ❌ External API timeout
- ❌ Invalid input data
- ❌ Code bug

**Resolution**:
1. Fix root cause (e.g., restart database)
2. Retry failed workflows from Temporal UI:
   - Click workflow → "Actions" → "Retry"
3. If widespread, consider code rollback

---

### Scenario 3: Slow Performance

**Symptoms**:
- Workflows taking longer than expected
- Queue depth growing

**Diagnosis**:
1. Grafana → PatientComet Dashboard
2. Check "Average Completion Time" graph
3. Identify when slowdown started
4. Jaeger → Search recent traces
5. Identify slow activities

**Common Causes**:
- ❌ Worker overloaded (too many concurrent activities)
- ❌ Database slow (check PostgreSQL metrics)
- ❌ Network latency
- ❌ Inefficient analyzer code

**Resolution**:
1. **Scale workers**: Add more worker instances
2. **Tune concurrency**: Reduce `max_concurrent_activities`
3. **Optimize activities**: Profile slow analyzers
4. **Add caching**: Cache expensive operations

---

### Scenario 4: Memory Issues

**Symptoms**:
- Worker OOM (out of memory)
- High memory usage in Grafana

**Diagnosis**:
1. Check worker memory: `docker stats velvetecho-worker`
2. Grafana → System Resources → Memory
3. Identify which component is consuming memory

**Common Causes**:
- ❌ Too many concurrent activities
- ❌ Activity memory leak
- ❌ Large workflow payloads

**Resolution**:
1. Reduce `max_concurrent_activities` to 25-30
2. Review activity code for leaks
3. Avoid passing large data through workflow results
4. Increase worker memory allocation

---

## 📋 Daily Operations Checklist

### Morning Health Check

```bash
# 1. Check infrastructure
docker ps  # All containers "Up"?

# 2. Check Temporal UI
open http://localhost:8088
# - Any stuck workflows?
# - High failure rate?

# 3. Check Grafana
open http://localhost:3000
# - System resources normal?
# - Error rates low?

# 4. Check recent workflows
# Temporal UI → Workflows → Sort by "Close Time"
# - Recent analyses completing successfully?
```

### Weekly Maintenance

```bash
# 1. Review metrics trends
# Grafana → Temporal Overview → Last 7 Days
# - Throughput stable?
# - Error rates trending up?

# 2. Check disk usage
docker exec velvetecho-postgresql df -h
# PostgreSQL using <80% disk?

# 3. Review slow activities
# Temporal UI → Search Attributes
# Filter: Duration > 5 minutes
# - Any analyzers consistently slow?

# 4. Clean up old workflows (optional)
# Temporal retention = 7 days (default)
# Consider increasing for audit requirements
```

---

## 🔧 Common Maintenance Tasks

### Restart Worker (Zero Downtime)

```bash
# 1. Start new worker instance
docker-compose up -d --scale worker=2

# 2. Verify new worker is processing
# Temporal UI → Check recent workflow assignments

# 3. Stop old worker
docker-compose up -d --scale worker=1
```

### Restart Temporal Server (With Downtime)

```bash
# 1. Stop accepting new workflows
# (Coordinate with team)

# 2. Wait for running workflows to complete
# Temporal UI → Check no "Running" workflows

# 3. Restart Temporal
docker-compose restart temporal

# 4. Verify health
curl http://localhost:7233/health
# Should return: SERVING
```

### Database Backup

```bash
# Backup PostgreSQL (Temporal state)
docker exec velvetecho-postgresql pg_dump -U temporal temporal > backup.sql

# Restore (if needed)
docker exec -i velvetecho-postgresql psql -U temporal temporal < backup.sql
```

### Clean Up Old Workflow History

Temporal auto-archives old workflows (default: 7 days).

**Manual cleanup**:
```bash
# Delete workflows older than 30 days
temporal workflow delete \
  --namespace default \
  --query "CloseTime < '30 days ago'"
```

---

## 📈 Performance Tuning

### Worker Tuning

**Current Settings** (default):
```yaml
max_concurrent_workflow_tasks: 10
max_concurrent_activities: 50
```

**Low Load** (<5 concurrent analyses):
```yaml
max_concurrent_workflow_tasks: 5
max_concurrent_activities: 25
```

**High Load** (>20 concurrent analyses):
```yaml
max_concurrent_workflow_tasks: 20
max_concurrent_activities: 100
```

**Recommendation**: Start conservative, scale up based on metrics.

---

### Database Tuning (PostgreSQL)

**For PatientComet workload** (many small transactions):

```sql
-- postgresql.conf
max_connections = 200
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
work_mem = 10MB
```

**Monitoring**:
```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Slow queries
SELECT query, mean_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

---

## 🚀 Scaling Guide

### Horizontal Scaling (Add Workers)

**When to scale**:
- Queue depth consistently >50
- Worker CPU >70%
- Throughput not meeting demand

**How to scale**:
```bash
# Add 2 more workers (total 3)
docker-compose up -d --scale worker=3

# Verify
docker ps | grep worker
# Should see 3 worker containers
```

**Auto-scaling** (Kubernetes):
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: velvetecho-worker
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: velvetecho-worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

### Vertical Scaling (Bigger Instances)

**Worker sizing**:

| Concurrent Analyses | CPU | Memory |
|---------------------|-----|--------|
| 1-5 | 2 cores | 4GB |
| 5-10 | 4 cores | 8GB |
| 10-20 | 8 cores | 16GB |

**Temporal sizing**:

| Workflows/sec | CPU | Memory | PostgreSQL |
|---------------|-----|--------|------------|
| <10 | 2 cores | 4GB | 2 cores, 4GB |
| 10-100 | 4 cores | 8GB | 4 cores, 8GB |
| >100 | 8+ cores | 16GB+ | 8 cores, 16GB |

---

## 📊 SLA Monitoring

### Recommended SLAs

| Metric | Target | Alert Threshold |
|--------|--------|----------------|
| **Availability** | 99.9% | <99.5% |
| **Workflow Success Rate** | >95% | <90% |
| **P50 Analysis Time** | <2 min | >5 min |
| **P95 Analysis Time** | <5 min | >10 min |
| **Activity Timeout Rate** | <1% | >5% |

### SLA Dashboard (Grafana)

**Panel 1: Availability**
```promql
(1 - (
  rate(temporal_workflow_execution_total{status="failed"}[24h])
  /
  rate(temporal_workflow_execution_total[24h])
)) * 100
```

**Panel 2: P95 Latency**
```promql
histogram_quantile(0.95,
  rate(temporal_workflow_execution_time_seconds_bucket[5m])
)
```

---

## 🔐 Security Operations

### Access Control

**Temporal UI Access**:
- Default: No authentication
- Production: Enable OAuth/SAML

**Database Access**:
- Restrict to VPN or internal network
- Use strong passwords
- Rotate credentials quarterly

### Audit Logging

**Workflow History**:
- All workflow events logged in PostgreSQL
- Retention: 7 days (configurable)
- Export for long-term audit:

```bash
# Export workflow history
temporal workflow show \
  --workflow-id my-workflow-123 \
  --output json > audit.json
```

---

## 📞 Escalation

### On-Call Escalation

**Level 1** (DevOps):
- Infrastructure issues (Docker, networking)
- Restart services
- Basic troubleshooting

**Level 2** (Engineering):
- Code bugs
- Performance optimization
- Complex debugging

**Level 3** (Architect):
- Design changes
- Capacity planning
- Major incidents

---

## ✅ Operations Checklist

**Daily**:
- [ ] Check Temporal UI for stuck/failed workflows
- [ ] Review Grafana dashboards
- [ ] Check alert status

**Weekly**:
- [ ] Review performance trends
- [ ] Check disk usage (PostgreSQL)
- [ ] Review slow activities
- [ ] Update on-call rotation

**Monthly**:
- [ ] Capacity planning review
- [ ] Performance optimization
- [ ] Backup verification
- [ ] Security audit

---

**Next**: See `TROUBLESHOOTING_FAQ.md` for common issues and solutions.
