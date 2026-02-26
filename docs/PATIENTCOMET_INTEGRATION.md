# PatientComet Integration Guide

**Status**: Pilot integration for VelvetEcho task orchestration

## Overview

PatientComet currently has:
- **111 analyzers** in a DAG execution pipeline
- Manual phase coordination via `DAGCoordinator`
- In-memory state management
- No retry/recovery mechanisms

With VelvetEcho, PatientComet will gain:
- **Durable workflows** - Survives crashes, restarts
- **Automatic retries** - Per-analyzer retry policies
- **Parallel execution** - Execute independent phases concurrently
- **Observability** - Temporal UI shows execution history, retry attempts
- **Scalability** - Horizontal scaling via worker pools

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ PatientComet API (FastAPI)                              │
│ /analysis/analyze endpoint                              │
└────────────────┬────────────────────────────────────────┘
                 │ Triggers workflow
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Temporal Workflow: run_analysis                         │
│ - Builds DAG from profile                               │
│ - Executes phases in topological order                  │
│ - Emits progress events                                 │
└────────────────┬────────────────────────────────────────┘
                 │ Executes activities
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Temporal Activities (111 analyzers)                     │
│ - execute_analyzer: Runs single analyzer                │
│ - persist_results: Saves to database                    │
│ - emit_event: Publishes progress                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ PatientComet Worker Pool (4-8 workers)                  │
│ - Polls "patientcomet-tasks" queue                      │
│ - Executes activities in parallel                       │
│ - Reports metrics to Temporal                           │
└─────────────────────────────────────────────────────────┘
```

## Implementation Steps

### Phase 1: Add VelvetEcho Dependency

```bash
cd /Users/antoineabdul-massih/Documents/patientcomet

# Add to pyproject.toml
poetry add velvetecho --path ../VelvetEcho
```

### Phase 2: Configure VelvetEcho

```python
# patientcomet/core/config.py

from velvetecho.config import VelvetEchoConfig

class Settings(BaseSettings):
    # ... existing fields ...

    # VelvetEcho configuration
    velvetecho: VelvetEchoConfig = VelvetEchoConfig(
        service_name="patientcomet",
        temporal_host="localhost:7233",
        temporal_namespace="patientcomet",
        redis_url="redis://localhost:6379/1",  # Different DB from default
        temporal_worker_count=8,  # High concurrency for analyzers
        temporal_max_concurrent_activities=50,
    )
```

### Phase 3: Convert Analyzers to Activities

**Before** (current):
```python
# patientcomet/analyzers/base.py
class BaseAnalyzer:
    async def execute(self, workspace_id: str) -> dict:
        # Analyzer logic
        pass
```

**After** (with VelvetEcho):
```python
from velvetecho.tasks import activity

@activity(
    start_to_close_timeout=300,  # 5 minutes per analyzer
    retry_policy={
        "max_attempts": 3,
        "backoff_coefficient": 2.0,
        "initial_interval": 5,
    }
)
async def execute_analyzer(
    analyzer_id: str,
    workspace_id: str,
    dependencies: dict,
) -> dict:
    """Execute a single analyzer as a Temporal activity"""
    analyzer = get_analyzer(analyzer_id)
    result = await analyzer.execute(workspace_id, dependencies)
    return result
```

### Phase 4: Create Analysis Workflow

```python
# patientcomet/workflows/analysis.py

from velvetecho.tasks import workflow, activity
from patientcomet.analysis.dag import build_dag
from patientcomet.storage.repositories import AnalysisRepository

@workflow(execution_timeout=7200)  # 2 hours max
async def run_analysis(
    workspace_id: str,
    profile: str = "full",
) -> dict:
    """
    Execute full PatientComet analysis pipeline.

    Phases are executed in DAG order with parallel execution
    of independent phases.
    """
    # Build phase DAG
    dag = build_dag(profile)

    # Track results
    results = {}

    # Execute phases in topological order
    for phase_batch in dag.get_execution_batches():
        # Execute all phases in this batch concurrently
        batch_tasks = [
            execute_analyzer.run(
                analyzer_id=phase.id,
                workspace_id=workspace_id,
                dependencies={
                    dep: results[dep]
                    for dep in phase.dependencies
                }
            )
            for phase in phase_batch
        ]

        batch_results = await asyncio.gather(*batch_tasks)

        # Store results
        for phase, result in zip(phase_batch, batch_results):
            results[phase.id] = result

            # Emit progress event
            await emit_progress.run(
                workspace_id=workspace_id,
                phase_id=phase.id,
                status="completed",
            )

    # Persist final results
    await persist_analysis.run(workspace_id, results)

    return {
        "workspace_id": workspace_id,
        "phases_completed": len(results),
        "status": "completed",
    }


@activity(start_to_close_timeout=30)
async def emit_progress(workspace_id: str, phase_id: str, status: str):
    """Emit progress event for SSE updates"""
    from patientcomet.events.bus import event_bus
    event_bus.emit("PHASE_COMPLETED", {
        "workspace_id": workspace_id,
        "phase_id": phase_id,
        "status": status,
    })


@activity(start_to_close_timeout=120)
async def persist_analysis(workspace_id: str, results: dict):
    """Persist analysis results to database"""
    repo = AnalysisRepository()
    await repo.save_results(workspace_id, results)
```

### Phase 5: Update API Route

```python
# patientcomet/api/routes/analysis.py

from velvetecho.tasks import get_client
from patientcomet.workflows.analysis import run_analysis

@router.post("/analyze")
async def trigger_analysis(workspace_id: str, profile: str = "full"):
    """Trigger analysis via Temporal workflow"""
    client = get_client()

    # Start workflow
    handle = await client.start_workflow(
        run_analysis,
        workspace_id,
        profile,
        workflow_id=f"analysis-{workspace_id}-{int(time.time())}",
    )

    return {
        "workflow_id": handle.id,
        "workspace_id": workspace_id,
        "status": "started",
    }


@router.get("/{workflow_id}/status")
async def get_analysis_status(workflow_id: str):
    """Get workflow execution status"""
    client = get_client()
    handle = await client.get_workflow_handle(workflow_id)

    try:
        result = await handle.result()
        return {"status": "completed", "result": result}
    except Exception:
        # Still running
        return {"status": "running"}
```

### Phase 6: Start Worker

```python
# patientcomet/worker.py

import asyncio
from velvetecho.tasks import WorkerManager, init_client
from patientcomet.core.config import settings
from patientcomet.workflows.analysis import (
    run_analysis,
    execute_analyzer,
    emit_progress,
    persist_analysis,
)

async def main():
    # Initialize client
    init_client(settings.velvetecho)

    # Create worker
    worker = WorkerManager(
        config=settings.velvetecho,
        workflows=[run_analysis],
        activities=[execute_analyzer, emit_progress, persist_analysis],
    )

    print(f"Starting PatientComet worker pool ({settings.velvetecho.temporal_worker_count} workers)")
    await worker.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### Phase 7: Update Startup Script

```bash
# scripts/start.sh

#!/bin/bash

# Start Temporal server (if not running)
temporal server start-dev &

# Start API server
uvicorn patientcomet.api.app:app --port 9800 &

# Start worker pool
python -m patientcomet.worker &

wait
```

## Benefits After Integration

### 1. **Durability**
- Analysis survives crashes → No need to restart from scratch
- Temporal persists state after each phase completes

### 2. **Observability**
- Temporal UI shows:
  - Current phase execution
  - Retry attempts
  - Execution history
  - Performance metrics per phase

### 3. **Scalability**
- Horizontal scaling: Add more workers
- No code changes needed

### 4. **Reliability**
- Automatic retries on failure
- Dead letter queue for permanently failed phases
- Circuit breaker prevents cascade failures

### 5. **Development Experience**
- Test workflows in isolation
- Mock activities for unit tests
- Replay production workflows locally

## Migration Strategy

**Week 1**: Setup & Configuration
- Add VelvetEcho dependency
- Configure Temporal connection
- Start Temporal dev server

**Week 2**: Workflow Implementation
- Convert 10 simple analyzers to activities
- Create basic workflow for those 10
- Test end-to-end with subset

**Week 3**: Full Migration
- Convert remaining 101 analyzers
- Update DAG execution to use workflow
- Maintain backward compatibility (can switch back)

**Week 4**: Production Rollout
- Deploy worker pool
- Monitor performance
- Remove legacy DAG coordinator

## Testing

```python
# tests/test_analysis_workflow.py

import pytest
from temporalio.testing import WorkflowEnvironment
from patientcomet.workflows.analysis import run_analysis, execute_analyzer

@pytest.mark.asyncio
async def test_analysis_workflow():
    """Test analysis workflow with mocked activities"""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Mock activity
        async def mock_execute_analyzer(analyzer_id, workspace_id, deps):
            return {"status": "success", "items": 10}

        # Run workflow
        result = await env.client.execute_workflow(
            run_analysis,
            "test-workspace",
            "quick",
            id="test-workflow",
            task_queue="test",
        )

        assert result["status"] == "completed"
```

## Performance Expectations

**Current** (without VelvetEcho):
- 134-file workspace: ~269 seconds
- Sequential execution
- No retry on failure
- No observability

**Expected** (with VelvetEcho):
- Same workspace: ~180 seconds (33% faster via parallelism)
- Automatic retries reduce manual intervention
- Temporal UI shows real-time progress
- Horizontal scaling via worker pool

## Next Steps

1. Install Temporal dev server: `brew install temporal`
2. Start Temporal: `temporal server start-dev`
3. Add VelvetEcho to PatientComet
4. Convert first 10 analyzers
5. Run integration test
