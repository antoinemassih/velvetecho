"""
Example: PatientComet integration with VelvetEcho

Demonstrates how PatientComet's 111-analyzer DAG would work with VelvetEcho.
"""

import asyncio
from velvetecho.config import VelvetEchoConfig, init_config
from velvetecho.tasks import workflow, activity
from velvetecho.patterns import DAGWorkflow, DAGNode
from velvetecho.monitoring import ProgressTracker


# Configure VelvetEcho for PatientComet
config = VelvetEchoConfig(
    service_name="patientcomet",
    temporal_host="localhost:7233",
    temporal_namespace="patientcomet",
    temporal_worker_count=8,
    temporal_max_concurrent_activities=50,  # High concurrency for analyzers
)
init_config(config)


# ============================================================================
# Activities (Analyzers)
# ============================================================================


@activity(
    start_to_close_timeout=300,
    retry_policy={
        "max_attempts": 3,
        "initial_interval": 5,
        "backoff_coefficient": 2.0,
    },
)
async def analyze_symbols(workspace_id: str, dependencies: dict) -> dict:
    """Phase 1: Symbol extraction (no dependencies)"""
    print(f"[analyze_symbols] Starting for workspace {workspace_id}")
    await asyncio.sleep(2)  # Simulate work
    return {"symbols": ["Symbol1", "Symbol2", "Symbol3"], "count": 3}


@activity(start_to_close_timeout=300, retry_policy={"max_attempts": 3})
async def analyze_imports(workspace_id: str, dependencies: dict) -> dict:
    """Phase 1: Import analysis (no dependencies)"""
    print(f"[analyze_imports] Starting for workspace {workspace_id}")
    await asyncio.sleep(2)
    return {"imports": ["import1", "import2"], "count": 2}


@activity(start_to_close_timeout=300, retry_policy={"max_attempts": 3})
async def analyze_types(workspace_id: str, dependencies: dict) -> dict:
    """Phase 1: Type analysis (no dependencies)"""
    print(f"[analyze_types] Starting for workspace {workspace_id}")
    await asyncio.sleep(2)
    return {"types": ["Type1", "Type2"], "count": 2}


@activity(start_to_close_timeout=300, retry_policy={"max_attempts": 3})
async def analyze_calls(workspace_id: str, dependencies: dict) -> dict:
    """Phase 2: Call graph (depends on symbols)"""
    symbols = dependencies["symbols"]
    print(f"[analyze_calls] Starting with {symbols['count']} symbols")
    await asyncio.sleep(3)
    return {"calls": ["call1", "call2"], "count": 2}


@activity(start_to_close_timeout=300, retry_policy={"max_attempts": 3})
async def analyze_data_flow(workspace_id: str, dependencies: dict) -> dict:
    """Phase 2: Data flow (depends on symbols + types)"""
    symbols = dependencies["symbols"]
    types = dependencies["types"]
    print(f"[analyze_data_flow] Starting with {symbols['count']} symbols, {types['count']} types")
    await asyncio.sleep(3)
    return {"flows": ["flow1", "flow2"], "count": 2}


@activity(start_to_close_timeout=300, retry_policy={"max_attempts": 3})
async def analyze_patterns(workspace_id: str, dependencies: dict) -> dict:
    """Phase 3: Pattern detection (depends on calls + data_flow)"""
    calls = dependencies["calls"]
    flows = dependencies["data_flow"]
    print(f"[analyze_patterns] Starting with {calls['count']} calls, {flows['count']} flows")
    await asyncio.sleep(4)
    return {"patterns": ["pattern1", "pattern2", "pattern3"], "count": 3}


# ============================================================================
# Workflow
# ============================================================================


@workflow(execution_timeout=7200)  # 2 hours max
async def run_patientcomet_analysis(workspace_id: str, profile: str = "quick") -> dict:
    """
    Execute PatientComet analysis pipeline with VelvetEcho.

    This example shows a simplified 6-analyzer DAG:
    - Phase 1 (parallel): symbols, imports, types
    - Phase 2 (parallel): calls, data_flow (depend on Phase 1)
    - Phase 3: patterns (depends on Phase 2)

    Real PatientComet has 111 analyzers with similar dependency structure.
    """
    print(f"Starting analysis for workspace {workspace_id} (profile: {profile})")

    # Create DAG
    dag = DAGWorkflow()

    # Phase 1: No dependencies (run in parallel)
    dag.add_nodes([
        DAGNode(id="symbols", execute=analyze_symbols.run, dependencies=[]),
        DAGNode(id="imports", execute=analyze_imports.run, dependencies=[]),
        DAGNode(id="types", execute=analyze_types.run, dependencies=[]),
    ])

    # Phase 2: Depend on Phase 1 (run in parallel)
    dag.add_nodes([
        DAGNode(id="calls", execute=analyze_calls.run, dependencies=["symbols"]),
        DAGNode(
            id="data_flow",
            execute=analyze_data_flow.run,
            dependencies=["symbols", "types"],
        ),
    ])

    # Phase 3: Depends on Phase 2
    dag.add_nodes([
        DAGNode(
            id="patterns",
            execute=analyze_patterns.run,
            dependencies=["calls", "data_flow"],
        ),
    ])

    # Progress callback (simulates SSE updates)
    def progress_callback(phase_id: str, status: str):
        print(f"[PROGRESS] Phase '{phase_id}': {status}")

    # Execute DAG (handles dependencies + parallelism automatically)
    results = await dag.execute(
        workspace_id=workspace_id,
        progress_callback=progress_callback,
    )

    print(f"Analysis complete! {len(results)} phases executed")

    return {
        "workspace_id": workspace_id,
        "profile": profile,
        "phases_completed": len(results),
        "results": results,
    }


# ============================================================================
# Real PatientComet Example (All 111 Analyzers)
# ============================================================================


@workflow(execution_timeout=7200)
async def run_full_patientcomet_analysis(workspace_id: str, profile: str = "full") -> dict:
    """
    Full PatientComet analysis with all 111 analyzers.

    This is how the real integration would look (simplified for readability).
    """
    dag = DAGWorkflow()

    # Phase 1: Core extraction (10 analyzers, no dependencies)
    phase1_analyzers = [
        "symbols", "files", "imports", "exports", "types",
        "classes", "functions", "variables", "constants", "enums",
    ]
    for analyzer_id in phase1_analyzers:
        dag.add_node(DAGNode(
            id=analyzer_id,
            execute=analyze_generic.run,  # Generic analyzer wrapper
            dependencies=[],
            metadata={"phase": 1},
        ))

    # Phase 2: Relationship extraction (15 analyzers, depend on Phase 1)
    phase2_analyzers = [
        ("calls", ["symbols", "functions"]),
        ("data_flows", ["symbols", "variables"]),
        ("control_flows", ["functions"]),
        ("inheritance", ["classes"]),
        ("implementations", ["classes"]),
        # ... 10 more
    ]
    for analyzer_id, deps in phase2_analyzers:
        dag.add_node(DAGNode(
            id=analyzer_id,
            execute=analyze_generic.run,
            dependencies=deps,
            metadata={"phase": 2},
        ))

    # Phase 3: Intelligence (20 analyzers, depend on Phase 1+2)
    # Phase 4: Quality metrics (15 analyzers)
    # Phase 5: Embeddings (5 analyzers)
    # ... etc for all 111 analyzers

    # Execute
    results = await dag.execute(workspace_id=workspace_id)

    return {"phases_completed": len(results), "results": results}


@activity(start_to_close_timeout=300, retry_policy={"max_attempts": 3})
async def analyze_generic(analyzer_id: str, workspace_id: str, dependencies: dict) -> dict:
    """Generic analyzer wrapper (real implementation would dispatch to specific analyzers)"""
    print(f"[{analyzer_id}] Executing...")
    await asyncio.sleep(1)
    return {"analyzer": analyzer_id, "status": "completed"}


# ============================================================================
# Client Usage
# ============================================================================


async def trigger_analysis():
    """Example: Triggering analysis from FastAPI endpoint"""
    from velvetecho.tasks import get_client, init_client

    # Initialize client
    client = init_client(config)
    await client.connect()

    # Start workflow
    print("Triggering analysis workflow...")
    handle = await client.start_workflow(
        run_patientcomet_analysis,
        "workspace-123",
        "quick",
        workflow_id=f"analysis-workspace-123-{int(asyncio.get_event_loop().time())}",
    )

    print(f"Workflow started: {handle.id}")
    print("Waiting for result...")

    # Wait for completion
    result = await handle.result()

    print(f"Analysis completed!")
    print(f"Phases: {result['phases_completed']}")
    print(f"Results: {result['results']}")

    await client.disconnect()


# ============================================================================
# Worker
# ============================================================================


async def run_worker():
    """Start PatientComet worker pool"""
    from velvetecho.tasks import WorkerManager

    worker = WorkerManager(
        config=config,
        workflows=[run_patientcomet_analysis, run_full_patientcomet_analysis],
        activities=[
            analyze_symbols,
            analyze_imports,
            analyze_types,
            analyze_calls,
            analyze_data_flow,
            analyze_patterns,
            analyze_generic,
        ],
    )

    print(f"PatientComet worker starting (queue: {config.task_queue})")
    print(f"Workers: {config.temporal_worker_count}")
    print(f"Max concurrent activities: {config.temporal_max_concurrent_activities}")
    print("Waiting for workflows...")

    await worker.start()


# ============================================================================
# Main
# ============================================================================


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python patientcomet_integration.py worker   # Start worker")
        print("  python patientcomet_integration.py client   # Trigger analysis")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "worker":
        asyncio.run(run_worker())
    elif mode == "client":
        asyncio.run(trigger_analysis())
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
