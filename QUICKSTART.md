# VelvetEcho Quick Start

## What is VelvetEcho?

**VelvetEcho** is a task orchestration library built on Temporal for your microservices ecosystem:
- CoralBeef, PatientComet, NeonPlane, Lobsterclaws, Whalefin, LunarBadger

It provides **durable workflows, automatic retries, parallel execution, and observability** without the complexity of building it yourself.

## Installation

### 1. Install Temporal (one-time setup)

```bash
# macOS
brew install temporal

# Or download from: https://github.com/temporalio/temporal
```

### 2. Start Temporal Dev Server

```bash
temporal server start-dev

# Temporal UI available at: http://localhost:8233
```

### 3. Add VelvetEcho to Your Service

```bash
cd /path/to/your-service

# Local development (edit VelvetEcho and see changes immediately)
poetry add velvetecho --path /Users/antoineabdul-massih/Documents/VelvetEcho

# Or from git (once pushed)
poetry add git+https://github.com/yourusername/velvetecho.git
```

## Basic Usage (5 Minutes)

### 1. Configure

```python
# your_service/config.py
from velvetecho.config import VelvetEchoConfig, init_config

config = VelvetEchoConfig(
    service_name="your-service",
    temporal_host="localhost:7233",
)
init_config(config)
```

### 2. Define Activities & Workflows

```python
# your_service/tasks.py
from velvetecho.tasks import workflow, activity

@activity(start_to_close_timeout=60)
async def process_data(data_id: str) -> dict:
    # Your business logic here
    return {"status": "processed"}

@workflow
async def my_workflow(data_id: str):
    result = await process_data.run(data_id)
    return result
```

### 3. Start Worker

```python
# your_service/worker.py
import asyncio
from velvetecho.tasks import WorkerManager
from your_service.config import config
from your_service.tasks import my_workflow, process_data

async def main():
    worker = WorkerManager(
        config=config,
        workflows=[my_workflow],
        activities=[process_data],
    )
    await worker.start()

if __name__ == "__main__":
    asyncio.run(main())
```

```bash
# Terminal 1: Start worker
python -m your_service.worker
```

### 4. Trigger from API

```python
# your_service/api.py
from fastapi import FastAPI
from velvetecho.tasks import get_client, init_client
from your_service.tasks import my_workflow

app = FastAPI()
init_client(config)

@app.post("/process")
async def trigger(data_id: str):
    client = get_client()
    handle = await client.start_workflow(my_workflow, data_id)
    return {"workflow_id": handle.id}
```

```bash
# Terminal 2: Start API
uvicorn your_service.api:app --reload

# Trigger workflow
curl -X POST "http://localhost:8000/process?data_id=123"
```

## Key Features

### Parallel Execution

```python
@workflow
async def analyze_files(file_paths: list[str]):
    # Execute all in parallel
    tasks = [analyze_file.run(path) for path in file_paths]
    results = await asyncio.gather(*tasks)
    return results
```

### Automatic Retries

```python
@activity(
    start_to_close_timeout=60,
    retry_policy={
        "max_attempts": 5,
        "backoff_coefficient": 2.0,  # Exponential backoff
        "initial_interval": 1,       # Start with 1 second
        "max_interval": 60,          # Cap at 60 seconds
    }
)
async def flaky_operation():
    # Will auto-retry on failure
    pass
```

### Long-Running Workflows

```python
@workflow(execution_timeout=86400)  # 24 hours
async def daily_report():
    # Survives server restarts
    data = await gather_data.run()
    await asyncio.sleep(3600)  # Wait 1 hour (durable!)
    report = await generate_report.run(data)
    return report
```

### Workflow Status

```python
# Check if workflow is still running
client = get_client()
handle = await client.get_workflow_handle("workflow-id")
result = await handle.result()  # Blocks until complete
```

## Project Structure

```
VelvetEcho/
├── velvetecho/
│   ├── config.py           # Configuration management
│   └── tasks/              # Task orchestration
│       ├── workflow.py     # @workflow decorator
│       ├── activity.py     # @activity decorator
│       ├── client.py       # Temporal client wrapper
│       └── worker.py       # Worker management
├── examples/
│   ├── basic_workflow.py   # Simple example
│   └── parallel_execution.py
├── tests/
│   ├── test_config.py
│   └── test_tasks.py
└── docs/
    └── PATIENTCOMET_INTEGRATION.md  # Detailed integration guide
```

## What's Next?

**Phase 2: API Framework** (Week 2-3)
- FastAPI router decorators
- Standard response formats
- Error handling middleware

**Phase 3: Cache & Queue** (Week 4)
- Redis patterns
- Circuit breakers
- Priority queues

## Resources

- **Temporal UI**: http://localhost:8233 (when dev server running)
- **Temporal Docs**: https://docs.temporal.io/
- **Example Project**: `examples/basic_workflow.py`
- **Integration Guide**: `docs/PATIENTCOMET_INTEGRATION.md`

## Getting Help

```python
# Configuration issues
from velvetecho.config import get_config
config = get_config()
print(config.model_dump())

# Check worker registration
worker = WorkerManager(config=config)
print(f"Task queue: {worker.task_queue}")
print(f"Workflows: {len(worker.workflows)}")
print(f"Activities: {len(worker.activities)}")
```

## Common Patterns

### Pattern: Pipeline with Dependencies

```python
@workflow
async def data_pipeline(input_data: dict):
    # Step 1
    validated = await validate_data.run(input_data)

    # Step 2 (depends on Step 1)
    enriched = await enrich_data.run(validated)

    # Step 3a and 3b (parallel, both depend on Step 2)
    analysis, report = await asyncio.gather(
        analyze_data.run(enriched),
        generate_report.run(enriched),
    )

    return {"analysis": analysis, "report": report}
```

### Pattern: Error Handling

```python
@activity
async def risky_operation():
    try:
        result = await external_api_call()
        return result
    except Exception as e:
        # Log error, emit metric, etc.
        logger.error("Operation failed", error=str(e))
        raise  # Re-raise for Temporal retry
```

### Pattern: Cancellation

```python
# From client
client = get_client()
await client.cancel_workflow("workflow-id")

# From within workflow
from velvetecho.tasks import workflow as wf
if wf.is_cancelled():
    # Cleanup logic
    return
```

---

**Built for**: CoralBeef, PatientComet, NeonPlane, Lobsterclaws, Whalefin, LunarBadger
**Version**: 0.1.0
**Status**: Phase 1 Complete (Task Orchestration)
