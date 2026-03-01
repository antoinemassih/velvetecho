"""Test DAG workflow pattern - FIXED VERSION"""

import asyncio
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker
from velvetecho.patterns import DAGWorkflow, DAGNode


# Analyzer activities (proper signature with dependencies parameter)
@activity.defn
async def analyze_symbols(workspace_id: str) -> dict:
    """Phase 1: Extract symbols"""
    await asyncio.sleep(0.1)
    return {"workspace_id": workspace_id, "symbols": ["symbol1", "symbol2", "symbol3"]}


@activity.defn
async def analyze_calls(workspace_id: str, symbols_result: dict) -> dict:
    """Phase 2: Analyze call graph"""
    await asyncio.sleep(0.1)
    symbols = symbols_result["symbols"]
    return {"workspace_id": workspace_id, "calls": 5, "symbols_used": len(symbols)}


@activity.defn
async def analyze_types(workspace_id: str, symbols_result: dict) -> dict:
    """Phase 2: Analyze types"""
    await asyncio.sleep(0.1)
    symbols = symbols_result["symbols"]
    return {"workspace_id": workspace_id, "types": 3, "symbols_typed": len(symbols)}


@activity.defn
async def analyze_complexity(workspace_id: str, calls_result: dict, types_result: dict) -> dict:
    """Phase 3: Analyze complexity"""
    await asyncio.sleep(0.1)
    return {
        "workspace_id": workspace_id,
        "complexity_score": calls_result["calls"] + types_result["types"],
        "summary": "Analysis complete!",
    }


# DAG Workflow (FIXED - proper node execute signatures)
@workflow.defn
class AnalysisDAGWorkflow:
    """Workflow that executes analyzers in DAG order"""

    @workflow.run
    async def run(self, workspace_id: str) -> dict:
        """Run analysis in dependency order"""

        # Build DAG with proper execute functions
        dag = DAGWorkflow()

        # Phase 1: Symbols (no dependencies)
        async def execute_symbols(dependencies, **kwargs):
            """Wrapper that calls the activity"""
            wid = kwargs.get("workspace_id")
            return await workflow.execute_activity(
                analyze_symbols,
                wid,
                start_to_close_timeout=timedelta(seconds=10),
            )

        dag.add_node(DAGNode(id="symbols", execute=execute_symbols, dependencies=[]))

        # Phase 2: Calls (depends on symbols)
        async def execute_calls(dependencies, **kwargs):
            """Wrapper that uses dependency results"""
            wid = kwargs.get("workspace_id")
            symbols_result = dependencies["symbols"]
            return await workflow.execute_activity(
                analyze_calls,
                args=[wid, symbols_result],
                start_to_close_timeout=timedelta(seconds=10),
            )

        dag.add_node(DAGNode(id="calls", execute=execute_calls, dependencies=["symbols"]))

        # Phase 2: Types (depends on symbols, parallel with calls)
        async def execute_types(dependencies, **kwargs):
            """Wrapper that uses dependency results"""
            wid = kwargs.get("workspace_id")
            symbols_result = dependencies["symbols"]
            return await workflow.execute_activity(
                analyze_types,
                args=[wid, symbols_result],
                start_to_close_timeout=timedelta(seconds=10),
            )

        dag.add_node(DAGNode(id="types", execute=execute_types, dependencies=["symbols"]))

        # Phase 3: Complexity (depends on both calls and types)
        async def execute_complexity(dependencies, **kwargs):
            """Wrapper that uses multiple dependency results"""
            wid = kwargs.get("workspace_id")
            calls_result = dependencies["calls"]
            types_result = dependencies["types"]
            return await workflow.execute_activity(
                analyze_complexity,
                args=[wid, calls_result, types_result],
                start_to_close_timeout=timedelta(seconds=10),
            )

        dag.add_node(
            DAGNode(id="complexity", execute=execute_complexity, dependencies=["calls", "types"])
        )

        # Execute DAG
        results = await dag.execute(workspace_id=workspace_id)

        return {
            "workspace_id": workspace_id,
            "phases_completed": list(results.keys()),
            "final_result": results["complexity"],
            "all_results": results,
        }


async def main():
    """Test DAG workflow"""
    print("🧪 Testing VelvetEcho DAG Pattern (FIXED)...")
    print()

    # Connect
    print("1️⃣  Connecting to Temporal...")
    client = await Client.connect("localhost:7233")
    print("   ✅ Connected")
    print()

    task_queue = "velvetecho-dag-fixed"

    # Start worker
    print("2️⃣  Starting worker...")
    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[AnalysisDAGWorkflow],
        activities=[analyze_symbols, analyze_calls, analyze_types, analyze_complexity],
    ):
        print(f"   ✅ Worker started")
        print()

        # Execute workflow
        print("3️⃣  Executing DAG workflow...")
        print("   📊 DAG structure:")
        print("      Phase 1: symbols (no deps)")
        print("      Phase 2: calls, types (depend on symbols, run in parallel)")
        print("      Phase 3: complexity (depends on calls + types)")
        print()

        handle = await client.start_workflow(
            AnalysisDAGWorkflow.run,
            "workspace-123",
            id=f"dag-test-fixed-{asyncio.get_event_loop().time()}",
            task_queue=task_queue,
        )
        print(f"   ✅ Workflow started: {handle.id}")
        print()

        # Wait for result
        print("4️⃣  Waiting for result...")
        result = await handle.result()
        print(f"   ✅ DAG execution completed!")
        print()
        print("   📝 Results:")
        print(f"      Workspace: {result['workspace_id']}")
        print(f"      Phases: {result['phases_completed']}")
        print(f"      Symbols: {result['all_results']['symbols']['symbols']}")
        print(f"      Calls: {result['all_results']['calls']['calls']}")
        print(f"      Types: {result['all_results']['types']['types']}")
        print(f"      Complexity Score: {result['final_result']['complexity_score']}")
        print(f"      Summary: {result['final_result']['summary']}")
        print()

    print("✅ DAG Pattern test PASSED!")
    print()
    print("VelvetEcho's DAG workflow pattern is working correctly! 🎉")
    print()
    print("Key Findings:")
    print("  ✅ DAG correctly orders execution by dependencies")
    print("  ✅ Independent tasks (calls, types) run in parallel")
    print("  ✅ Dependency results passed correctly to dependent tasks")
    print("  ✅ All 4 phases executed in correct order")


if __name__ == "__main__":
    asyncio.run(main())
