# VelvetEcho - Getting Started Guide

**Last Updated**: 2026-03-01
**Version**: 1.0
**Audience**: PatientComet Integration Team

---

## 🎯 What is VelvetEcho?

VelvetEcho is a **task orchestration framework** built on [Temporal](https://temporal.io) for managing complex, multi-step workflows with:

- ✅ **DAG Pattern**: Define workflows as directed acyclic graphs with dependencies
- ✅ **Parallel Execution**: Run independent tasks concurrently
- ✅ **Fault Tolerance**: Automatic retries, circuit breakers
- ✅ **Durable Execution**: Workflows survive crashes and restarts
- ✅ **Full Observability**: Temporal UI, Prometheus metrics, Jaeger tracing

**Perfect For**: PatientComet's 111-analyzer code intelligence pipeline

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites

- Python 3.11+
- Docker Desktop
- 8GB RAM minimum

### 1. Clone Repository

```bash
cd /Users/antoineabdul-massih/Documents
git clone <velvetecho-repo-url>
cd VelvetEcho
```

### 2. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Start Infrastructure

```bash
docker-compose up -d
```

**Services Started**:
- ✅ Temporal (localhost:7233)
- ✅ Temporal UI (localhost:8088)
- ✅ PostgreSQL (localhost:5432)
- ✅ Redis (localhost:6379)
- ✅ Prometheus (localhost:9090)
- ✅ Grafana (localhost:3000)
- ✅ Jaeger (localhost:16686)

**Verify**: Open http://localhost:8088 (Temporal UI)

### 4. Run Example Workflow

```bash
python examples/simple_dag_example.py
```

**Expected Output**:
```
🚀 Starting simple DAG workflow
✅ Workflow completed: workflow-123
📊 Results: 4 phases completed in 0.8s
```

**View in Temporal UI**: http://localhost:8088/namespaces/default/workflows

---

## 📚 Core Concepts

### 1. Workflows

**Workflows** are the main orchestration logic. They must be class-based (Temporal requirement):

```python
from temporalio import workflow
from datetime import timedelta

@workflow.defn
class MyWorkflow:
    """Workflow that orchestrates tasks"""

    @workflow.run
    async def run(self, input_data: str) -> dict:
        # Your workflow logic here
        result = await workflow.execute_activity(
            my_activity,
            input_data,
            start_to_close_timeout=timedelta(seconds=10),
        )
        return {"status": "completed", "result": result}
```

**Key Points**:
- Must use `@workflow.defn` decorator
- Must have `@workflow.run` method
- Must be class-based (no function workflows)

---

### 2. Activities

**Activities** are the actual work units (analyzers, API calls, database operations):

```python
from temporalio import activity

@activity.defn
async def my_activity(data: str) -> dict:
    """Activity that does actual work"""
    # This can fail, will be retried automatically
    result = await some_expensive_operation(data)
    return {"processed": result}
```

**Key Points**:
- Can fail and retry (unlike workflows)
- Can call external APIs, databases
- Should be idempotent (safe to retry)

---

### 3. DAG Pattern (VelvetEcho's Core Feature)

**DAG** = Directed Acyclic Graph. Define workflows with dependencies:

```python
from velvetecho.patterns import DAGWorkflow, DAGNode

dag = DAGWorkflow()

# Phase 1: No dependencies
dag.add_node(DAGNode(
    id="extract_symbols",
    execute=extract_symbols_func,
    dependencies=[]  # Runs first
))

# Phase 2: Depends on Phase 1
dag.add_node(DAGNode(
    id="build_call_graph",
    execute=build_call_graph_func,
    dependencies=["extract_symbols"]  # Waits for symbols
))

dag.add_node(DAGNode(
    id="analyze_types",
    execute=analyze_types_func,
    dependencies=["extract_symbols"]  # Also waits for symbols
))

# Phase 2a and 2b run IN PARALLEL!

# Phase 3: Depends on both Phase 2 tasks
dag.add_node(DAGNode(
    id="final_analysis",
    execute=final_analysis_func,
    dependencies=["build_call_graph", "analyze_types"]
))

# Execute
results = await dag.execute()
```

**Key Benefits**:
- ✅ Automatic parallelization (independent tasks run concurrently)
- ✅ Automatic dependency resolution
- ✅ Automatic execution ordering

---

### 4. Workers

**Workers** execute workflows and activities:

```python
from temporalio.client import Client
from temporalio.worker import Worker

async def run_worker():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="my-task-queue",
        workflows=[MyWorkflow],
        activities=[my_activity],
        max_concurrent_activities=50,  # Run up to 50 activities in parallel
    )

    await worker.run()
```

**Start Worker**:
```bash
python my_worker.py
```

**Worker stays running**, polling Temporal for work.

---

## 🎓 Example: PatientComet Analyzer

### Step 1: Define Activity

**File**: `patientcomet_activities.py`

```python
from temporalio import activity
from patientcomet.analyzers import SymbolExtractionAnalyzer

@activity.defn
async def analyze_symbols(workspace_id: str) -> dict:
    """Extract symbols from codebase"""
    analyzer = SymbolExtractionAnalyzer()
    await analyzer.initialize(workspace_id)
    result = await analyzer.execute()

    return {
        "workspace_id": workspace_id,
        "symbols_count": len(result["symbols"]),
        "output": result
    }
```

### Step 2: Define Workflow

**File**: `patientcomet_workflow.py`

```python
from temporalio import workflow
from datetime import timedelta
from velvetecho.patterns import DAGWorkflow, DAGNode
from patientcomet_activities import analyze_symbols

@workflow.defn
class PatientCometAnalysisWorkflow:
    """Orchestrates PatientComet analyzers"""

    @workflow.run
    async def run(self, workspace_id: str) -> dict:
        dag = DAGWorkflow()

        # Add symbol extraction (no dependencies)
        async def exec_symbols(dependencies, **kwargs):
            return await workflow.execute_activity(
                analyze_symbols,
                workspace_id,
                start_to_close_timeout=timedelta(seconds=300),
            )

        dag.add_node(DAGNode(
            id="symbol_extraction",
            execute=exec_symbols,
            dependencies=[]
        ))

        # Execute DAG
        results = await dag.execute(workspace_id=workspace_id)

        return {
            "workspace_id": workspace_id,
            "analyzers_completed": len(results),
            "results": results
        }
```

### Step 3: Create Worker

**File**: `patientcomet_worker.py`

```python
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from patientcomet_workflow import PatientCometAnalysisWorkflow
from patientcomet_activities import analyze_symbols

async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="patientcomet-analysis",
        workflows=[PatientCometAnalysisWorkflow],
        activities=[analyze_symbols],
    )

    print("🚀 Worker started")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 4: Start Worker

```bash
python patientcomet_worker.py
```

**Output**:
```
🚀 Worker started
```

### Step 5: Trigger Workflow

**File**: `trigger_analysis.py`

```python
import asyncio
from temporalio.client import Client
from patientcomet_workflow import PatientCometAnalysisWorkflow

async def main():
    client = await Client.connect("localhost:7233")

    # Start workflow
    handle = await client.start_workflow(
        PatientCometAnalysisWorkflow.run,
        "workspace-123",  # workspace_id
        id=f"analysis-{time.time()}",
        task_queue="patientcomet-analysis",
    )

    print(f"Started workflow: {handle.id}")
    print(f"View: http://localhost:8088")

    # Wait for result
    result = await handle.result()
    print(f"Completed: {result['analyzers_completed']} analyzers")

if __name__ == "__main__":
    asyncio.run(main())
```

**Run**:
```bash
python trigger_analysis.py
```

**Output**:
```
Started workflow: analysis-1709318400
View: http://localhost:8088
Completed: 1 analyzers
```

---

## 🔍 Monitoring Your Workflows

### Temporal UI (Primary)

**URL**: http://localhost:8088

**Features**:
- 🔍 Search workflows by ID, status, type
- 📊 View execution history (all steps)
- ⏱️ See timing for each activity
- 🔁 View retry attempts
- ❌ Stack traces for failures
- ▶️ Pause/resume/cancel workflows

**Navigation**:
1. Open http://localhost:8088
2. Click "Workflows" in sidebar
3. Find your workflow by ID
4. Click to see full execution timeline

### Prometheus (Metrics)

**URL**: http://localhost:9090

**Useful Queries**:
```promql
# Workflow duration
temporal_workflow_execution_time_seconds

# Activity failures
temporal_activity_execution_failed_total

# Active workflows
temporal_workflow_active_total
```

### Grafana (Dashboards)

**URL**: http://localhost:3000
**Login**: admin/admin

**Pre-built Dashboards**:
- Temporal Overview
- Workflow Performance
- Activity Metrics

---

## 🐛 Debugging

### Common Issues

#### 1. "Worker not found for task queue"

**Problem**: No worker running for your task queue
**Fix**:
```bash
# Start the worker
python patientcomet_worker.py
```

#### 2. "Activity timeout"

**Problem**: Activity takes longer than `start_to_close_timeout`
**Fix**: Increase timeout
```python
await workflow.execute_activity(
    my_activity,
    start_to_close_timeout=timedelta(seconds=600),  # 10 minutes
)
```

#### 3. "Workflow failed with error: ..."

**Check Temporal UI**:
1. Open http://localhost:8088
2. Find your workflow
3. Click "Stack Trace" tab
4. See full error details

---

## 📖 Next Steps

1. ✅ **Read**: `VELVETECHO_ARCHITECTURE.md` - Understand system design
2. ✅ **Read**: `PATIENTCOMET_INTEGRATION_PLAN.md` - Integration roadmap
3. ✅ **Practice**: Run `examples/dag_workflow_example.py`
4. ✅ **Build**: Implement 1 PatientComet analyzer as activity
5. ✅ **Test**: Run end-to-end with worker + workflow

---

## 🆘 Getting Help

**Documentation**:
- VelvetEcho: `/Users/antoineabdul-massih/Documents/VelvetEcho/docs/`
- Temporal: https://docs.temporal.io

**Temporal UI**: http://localhost:8088
**Monitoring**: http://localhost:3000 (Grafana)

**Common Commands**:
```bash
# Start infrastructure
docker-compose up -d

# Stop infrastructure
docker-compose down

# View logs
docker-compose logs -f temporal

# Restart services
docker-compose restart
```

---

## ✅ Quick Reference

| Task | Command |
|------|---------|
| Start infrastructure | `docker-compose up -d` |
| Stop infrastructure | `docker-compose down` |
| Start worker | `python my_worker.py` |
| Trigger workflow | `python trigger_workflow.py` |
| View workflows | http://localhost:8088 |
| View metrics | http://localhost:9090 |
| View dashboards | http://localhost:3000 |

---

**You're ready!** Start with the simple example, then move to integrating PatientComet analyzers using the pattern above.
