# VelvetEcho Use Case Patterns

Real-world implementation patterns for CoralBeef ecosystem services.

## Scenario 1: PatientComet - DAG Execution with Dependencies

**Challenge**: Execute 111+ analyzers with complex dependencies, stream progress in real-time.

### Current Architecture (Without VelvetEcho)

```python
# patientcomet/analysis/dag.py
class DAGCoordinator:
    async def execute(self, workspace_id: str):
        # Build dependency graph
        phases = self.build_dag()

        # Execute in topological order
        for batch in phases:
            for phase in batch:
                result = await self.execute_phase(phase)
                self.results[phase.id] = result
```

**Problems**:
- No retry on failure
- Crashes lose all progress
- Manual progress tracking
- No horizontal scaling

### With VelvetEcho

```python
# patientcomet/workflows/analysis.py
from velvetecho.tasks import workflow, activity
from velvetecho.patterns import dag_workflow
import asyncio

@activity(
    start_to_close_timeout=300,
    retry_policy={"max_attempts": 3, "initial_interval": 5}
)
async def execute_analyzer(
    analyzer_id: str,
    workspace_id: str,
    dependency_results: dict,
    progress_callback: str,  # Workflow ID for progress updates
) -> dict:
    """
    Execute a single analyzer as a durable activity.

    - Automatically retries on failure
    - Reports progress via heartbeat
    - Results are persisted by Temporal
    """
    from temporalio import activity
    from patientcomet.analyzers import get_analyzer

    analyzer = get_analyzer(analyzer_id)

    # Report progress via heartbeat (keeps activity alive + streams progress)
    activity.heartbeat({"status": "started", "analyzer": analyzer_id})

    try:
        # Execute with dependencies
        result = await analyzer.execute(workspace_id, dependency_results)

        # Report completion
        activity.heartbeat({"status": "completed", "analyzer": analyzer_id, "items": len(result)})

        return result
    except Exception as e:
        # Report error (will trigger retry)
        activity.heartbeat({"status": "failed", "analyzer": analyzer_id, "error": str(e)})
        raise


@workflow(execution_timeout=7200)  # 2 hours max
async def run_analysis(workspace_id: str, profile: str = "full") -> dict:
    """
    Execute PatientComet analysis pipeline as a durable workflow.

    Benefits:
    - Survives crashes (Temporal replays from last checkpoint)
    - Automatic retries per analyzer
    - Parallel execution of independent phases
    - Progress streaming via heartbeat
    """
    from patientcomet.analysis.dag import build_dag_from_profile

    # Build DAG (deterministic!)
    dag = build_dag_from_profile(profile)

    # Track results
    results = {}

    # Execute phases in batches (topological order)
    for batch in dag.get_execution_batches():
        # All phases in batch are independent → execute in parallel
        batch_tasks = []

        for phase in batch:
            # Gather dependency results
            dependency_results = {
                dep_id: results[dep_id]
                for dep_id in phase.dependencies
            }

            # Start activity
            task = execute_analyzer.run(
                analyzer_id=phase.id,
                workspace_id=workspace_id,
                dependency_results=dependency_results,
                progress_callback=workflow.info().workflow_id,
            )
            batch_tasks.append(task)

        # Wait for all phases in batch to complete
        batch_results = await asyncio.gather(*batch_tasks)

        # Store results
        for phase, result in zip(batch, batch_results):
            results[phase.id] = result

    return {
        "workspace_id": workspace_id,
        "phases_completed": len(results),
        "status": "completed",
        "results": results,
    }
```

### Progress Streaming

VelvetEcho provides **two mechanisms** for progress streaming:

#### Option A: Activity Heartbeat (Recommended)

```python
# In your activity
from temporalio import activity

@activity
async def execute_analyzer(analyzer_id, workspace_id, ...):
    # Send progress updates
    activity.heartbeat({"phase": analyzer_id, "progress": 0, "status": "started"})

    result = await analyzer.execute()

    activity.heartbeat({"phase": analyzer_id, "progress": 100, "status": "completed"})
    return result
```

```python
# In your API route (SSE endpoint)
from velvetecho.tasks import get_client

@router.get("/analysis/{workflow_id}/progress")
async def stream_progress(workflow_id: str):
    """Stream progress updates via SSE"""
    client = get_client()
    handle = await client.get_workflow_handle(workflow_id)

    async def event_generator():
        # Poll for heartbeat details
        while True:
            try:
                # Query workflow for current progress
                progress = await handle.query("get_progress")
                yield f"data: {json.dumps(progress)}\n\n"
                await asyncio.sleep(1)
            except:
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

#### Option B: Signal Pattern (More Control)

```python
@workflow
async def run_analysis(workspace_id: str, profile: str):
    # Store progress state
    progress_state = {"completed": 0, "total": 111, "current": None}

    # Define signal handler for progress queries
    @workflow.query
    def get_progress():
        return progress_state

    # Execute analyzers
    for phase in phases:
        progress_state["current"] = phase.id
        result = await execute_analyzer.run(...)
        progress_state["completed"] += 1

    return results
```

### Dependency Management

VelvetEcho handles dependencies via **workflow state**:

```python
# Example: Phase E depends on outputs from Phase A, B, C
@workflow
async def run_analysis(workspace_id: str):
    # Phase 1: Independent phases (parallel)
    result_a = await analyzer_a.run(workspace_id, {})
    result_b = await analyzer_b.run(workspace_id, {})
    result_c = await analyzer_c.run(workspace_id, {})

    # Phase 2: Depends on Phase 1 (waits for all)
    result_d = await analyzer_d.run(workspace_id, {
        "symbols": result_a,      # Depends on A
        "types": result_b,         # Depends on B
    })

    # Phase 3: Depends on everything
    result_e = await analyzer_e.run(workspace_id, {
        "symbols": result_a,
        "types": result_b,
        "calls": result_c,
        "patterns": result_d,
    })

    return result_e
```

**Key Point**: Workflow state is **automatically persisted** by Temporal after each activity completes.

### Real DAG Example

```python
# patientcomet/workflows/analysis.py

@workflow
async def run_analysis(workspace_id: str, profile: str):
    """Execute 111 analyzers with dependencies"""

    # Batch 1: No dependencies (10 analyzers run in parallel)
    [symbols, files, imports, exports, types, classes, functions,
     variables, constants, enums] = await asyncio.gather(
        analyzer_symbols.run(workspace_id, {}),
        analyzer_files.run(workspace_id, {}),
        analyzer_imports.run(workspace_id, {}),
        analyzer_exports.run(workspace_id, {}),
        analyzer_types.run(workspace_id, {}),
        analyzer_classes.run(workspace_id, {}),
        analyzer_functions.run(workspace_id, {}),
        analyzer_variables.run(workspace_id, {}),
        analyzer_constants.run(workspace_id, {}),
        analyzer_enums.run(workspace_id, {}),
    )

    # Batch 2: Depend on Batch 1 (15 analyzers run in parallel)
    [calls, data_flows, control_flows, ...] = await asyncio.gather(
        analyzer_calls.run(workspace_id, {"symbols": symbols, "functions": functions}),
        analyzer_data_flows.run(workspace_id, {"symbols": symbols, "variables": variables}),
        analyzer_control_flows.run(workspace_id, {"functions": functions}),
        # ... 12 more
    )

    # Batch 3: Depend on Batch 1+2 (20 analyzers run in parallel)
    [patterns, architectures, coupling, ...] = await asyncio.gather(
        analyzer_patterns.run(workspace_id, {
            "symbols": symbols,
            "calls": calls,
            "data_flows": data_flows,
        }),
        # ... 19 more
    )

    # ... Continue for all 111 analyzers

    return {"symbols": symbols, "calls": calls, "patterns": patterns, ...}
```

**Benefits**:
- ✅ **Crash Recovery**: If Python crashes at Batch 2, Temporal replays Batch 1 from history (instant), continues from Batch 2
- ✅ **Automatic Retries**: Failed analyzer retries 3x with backoff
- ✅ **Parallelism**: 10-20 analyzers run concurrently per batch
- ✅ **Progress Tracking**: Heartbeats show exactly which analyzer is running
- ✅ **Horizontal Scaling**: Add more workers → more parallel execution

---

## Scenario 2: Urchinspike - Parallel Tool Execution

**Challenge**: Execute 50+ Urchinspike tools in parallel, collect results.

### With VelvetEcho

```python
# urchinspike/workflows/batch_execution.py

@activity(start_to_close_timeout=120)
async def execute_tool(tool_name: str, tool_args: dict, context: dict) -> dict:
    """Execute a single Urchinspike tool"""
    from temporalio import activity
    from urchinspike.registry import get_tool

    tool = get_tool(tool_name)

    # Report start
    activity.heartbeat({"tool": tool_name, "status": "running"})

    try:
        result = await tool.execute(**tool_args)

        # Report completion
        activity.heartbeat({"tool": tool_name, "status": "completed"})

        return {
            "tool": tool_name,
            "status": "success",
            "result": result,
        }
    except Exception as e:
        activity.heartbeat({"tool": tool_name, "status": "failed", "error": str(e)})
        raise


@workflow(execution_timeout=600)
async def execute_tool_batch(
    tool_requests: list[dict],  # [{"name": "read_file", "args": {...}}, ...]
    context: dict,
    max_parallelism: int = 10,
) -> dict:
    """
    Execute multiple tools in parallel with concurrency control.

    Args:
        tool_requests: List of tools to execute
        context: Shared context (workspace_id, session_id, etc.)
        max_parallelism: Max tools running at once

    Returns:
        {"results": [...], "succeeded": 48, "failed": 2}
    """
    results = []
    succeeded = 0
    failed = 0

    # Execute in chunks (respect max_parallelism)
    for i in range(0, len(tool_requests), max_parallelism):
        chunk = tool_requests[i:i+max_parallelism]

        # Execute chunk in parallel
        tasks = [
            execute_tool.run(
                tool_name=req["name"],
                tool_args=req["args"],
                context=context,
            )
            for req in chunk
        ]

        # Wait for chunk to complete
        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in chunk_results:
            if isinstance(result, Exception):
                failed += 1
                results.append({"status": "error", "error": str(result)})
            else:
                succeeded += 1
                results.append(result)

    return {
        "results": results,
        "total": len(tool_requests),
        "succeeded": succeeded,
        "failed": failed,
    }
```

### Usage from Lobsterclaws

```python
# lobsterclaws/execution/tool_executor.py

from velvetecho.tasks import get_client

async def execute_tools_async(session_id: str, tool_requests: list):
    """Execute tools asynchronously via VelvetEcho"""
    client = get_client()

    # Start workflow
    handle = await client.start_workflow(
        execute_tool_batch,
        tool_requests,
        context={"session_id": session_id},
        max_parallelism=10,
        workflow_id=f"tools-{session_id}-{int(time.time())}",
    )

    # Return handle for progress tracking
    return {
        "workflow_id": handle.id,
        "status": "running",
    }

async def get_tool_execution_status(workflow_id: str):
    """Get status of tool batch execution"""
    client = get_client()
    handle = await client.get_workflow_handle(workflow_id)

    try:
        result = await handle.result()
        return {"status": "completed", "result": result}
    except:
        # Still running
        progress = await handle.query("get_progress")
        return {"status": "running", "progress": progress}
```

---

## Scenario 3: Whalefin - Session Queuing + Parallel Sessions

**Challenge**:
- Serial requests on same session (queue them)
- Parallel requests across different sessions
- All must communicate state back

### Pattern A: Session Workflow (Long-Running)

Each agent session = One long-running workflow

```python
# whalefin/workflows/session.py

@workflow
async def agent_session(
    session_id: str,
    agent_id: str,
    initial_request: dict,
) -> None:
    """
    Long-running workflow representing an agent session.

    - Handles multiple requests serially (queued)
    - Uses signals to receive new requests
    - Uses queries to get state
    - Runs until explicitly terminated
    """
    from temporalio import workflow

    # Session state
    state = {
        "session_id": session_id,
        "agent_id": agent_id,
        "requests": [initial_request],  # Queue of pending requests
        "history": [],                   # Completed requests
        "current_request": None,
        "status": "active",
    }

    # Signal handler: Add new request to queue
    @workflow.signal
    def add_request(request: dict):
        state["requests"].append(request)

    # Signal handler: Terminate session
    @workflow.signal
    def terminate():
        state["status"] = "terminated"

    # Query handler: Get current state
    @workflow.query
    def get_state():
        return {
            "session_id": state["session_id"],
            "agent_id": state["agent_id"],
            "queued_requests": len(state["requests"]),
            "completed_requests": len(state["history"]),
            "current_request": state["current_request"],
            "status": state["status"],
        }

    # Main loop: Process requests from queue
    while state["status"] == "active":
        if state["requests"]:
            # Get next request from queue
            request = state["requests"].pop(0)
            state["current_request"] = request

            # Execute request as activity
            try:
                result = await execute_agent_request.run(
                    agent_id=agent_id,
                    session_id=session_id,
                    request=request,
                )

                # Store in history
                state["history"].append({
                    "request": request,
                    "result": result,
                    "status": "success",
                })
            except Exception as e:
                state["history"].append({
                    "request": request,
                    "error": str(e),
                    "status": "failed",
                })

            state["current_request"] = None
        else:
            # No pending requests, wait for signal
            await workflow.wait_condition(lambda: len(state["requests"]) > 0 or state["status"] != "active")


@activity(start_to_close_timeout=300)
async def execute_agent_request(
    agent_id: str,
    session_id: str,
    request: dict,
) -> dict:
    """Execute a single agent request"""
    from temporalio import activity
    from whalefin.agents import get_agent

    agent = get_agent(agent_id)

    # Report progress
    activity.heartbeat({"session": session_id, "status": "thinking"})

    # Execute
    result = await agent.execute(request["prompt"], context=request.get("context"))

    # Report completion
    activity.heartbeat({"session": session_id, "status": "completed"})

    return result
```

### Usage

```python
# whalefin/api/routes/sessions.py

@router.post("/sessions/{session_id}/requests")
async def add_request_to_session(session_id: str, request: dict):
    """Add a new request to existing session (queues it)"""
    client = get_client()

    # Get workflow handle for session
    workflow_id = f"session-{session_id}"
    handle = await client.get_workflow_handle(workflow_id)

    # Send signal to add request to queue
    await handle.signal("add_request", request)

    # Get updated state
    state = await handle.query("get_state")

    return {
        "session_id": session_id,
        "queued_requests": state["queued_requests"],
        "position_in_queue": state["queued_requests"],
    }


@router.get("/sessions/{session_id}/state")
async def get_session_state(session_id: str):
    """Get current session state"""
    client = get_client()

    workflow_id = f"session-{session_id}"
    handle = await client.get_workflow_handle(workflow_id)

    state = await handle.query("get_state")

    return state
```

### Pattern B: Parallel Sessions

Multiple sessions = Multiple workflows running in parallel

```python
# Start 5 parallel sessions
client = get_client()

session_handles = await asyncio.gather(*[
    client.start_workflow(
        agent_session,
        session_id=f"session-{i}",
        agent_id="code-analyst",
        initial_request={"prompt": f"Analyze file {i}"},
        workflow_id=f"session-{i}",
    )
    for i in range(5)
])

# All 5 sessions run in parallel
# Each session processes its own queue serially
```

### State Communication Pattern

**Option 1: Shared State via Redis**

```python
@activity
async def execute_agent_request(agent_id, session_id, request):
    from velvetecho.cache import RedisCache

    cache = RedisCache()

    # Read shared state
    shared_state = await cache.get(f"agent:{agent_id}:shared_state")

    # Execute with shared state
    result = await agent.execute(request, shared_state=shared_state)

    # Update shared state
    await cache.set(f"agent:{agent_id}:shared_state", result["new_state"])

    return result
```

**Option 2: Cross-Workflow Signals**

```python
# Session A signals Session B
client = get_client()
session_b = await client.get_workflow_handle("session-B")
await session_b.signal("receive_state_update", {"from": "session-A", "data": {...}})
```

---

## Summary Table

| Scenario | Pattern | Parallelism | State | Progress |
|----------|---------|-------------|-------|----------|
| **PatientComet** | DAG Workflow | Batch-level (`asyncio.gather`) | Workflow state | Heartbeat |
| **Urchinspike** | Tool Batch | Chunked parallelism | Activity results | Heartbeat |
| **Whalefin Serial** | Session Workflow + Queue | Sequential (FIFO) | Workflow state + Signals/Queries | Activity heartbeat |
| **Whalefin Parallel** | Multiple Session Workflows | Workflow-level | Redis or Signals | Per-session heartbeat |

## Next Steps

1. **PatientComet**: Implement DAG workflow with first 10 analyzers
2. **Urchinspike**: Add tool batch execution workflow
3. **Whalefin**: Implement session workflow pattern
