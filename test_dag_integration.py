"""Test DAG workflow pattern (core VelvetEcho feature)"""

import asyncio
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker
from velvetecho.patterns import DAGWorkflow, DAGNode


# Simulate analyzer activities
@activity.defn
async def analyze_symbols(workspace_id: str) -> dict:
    """Phase 1: Extract symbols"""
    await asyncio.sleep(0.1)  # Simulate work
    return {workspace_id: ["symbol1", "symbol2", "symbol3"]}


@activity.defn
async def analyze_calls(workspace_id: str, symbols: dict) -> dict:
    """Phase 2: Analyze call graph (depends on symbols)"""
    await asyncio.sleep(0.1)
    return {workspace_id: {"calls": 5, "symbols_used": len(symbols[workspace_id])}}


@activity.defn
async def analyze_types(workspace_id: str, symbols: dict) -> dict:
    """Phase 2: Analyze types (depends on symbols, parallel with calls)"""
    await asyncio.sleep(0.1)
    return {workspace_id: {"types": 3, "symbols_typed": len(symbols[workspace_id])}}


@activity.defn
async def analyze_complexity(workspace_id: str, calls: dict, types: dict) -> dict:
    """Phase 3: Analyze complexity (depends on both calls and types)"""
    await asyncio.sleep(0.1)
    return {
        workspace_id: {
            "complexity_score": calls[workspace_id]["calls"] + types[workspace_id]["types"],
            "summary": "Analysis complete!",
        }
    }


# DAG Workflow
@workflow.defn
class AnalysisDAGWorkflow:
    """Workflow that executes analyzers in DAG order"""

    @workflow.run
    async def run(self, workspace_id: str) -> dict:
        """Run analysis in dependency order"""

        # Build DAG
        dag = DAGWorkflow()

        # Phase 1: Symbols (no dependencies)
        dag.add_node(
            DAGNode(
                id="symbols",
                execute=lambda wid: workflow.execute_activity(
                    analyze_symbols,
                    wid,
                    start_to_close_timeout=timedelta(seconds=10),
                ),
                dependencies=[],
            )
        )

        # Phase 2: Calls and Types (depend on symbols, can run in parallel)
        dag.add_node(
            DAGNode(
                id="calls",
                execute=lambda wid, results: workflow.execute_activity(
                    analyze_calls,
                    args=[wid, results["symbols"]],
                    start_to_close_timeout=timedelta(seconds=10),
                ),
                dependencies=["symbols"],
            )
        )

        dag.add_node(
            DAGNode(
                id="types",
                execute=lambda wid, results: workflow.execute_activity(
                    analyze_types,
                    args=[wid, results["symbols"]],
                    start_to_close_timeout=timedelta(seconds=10),
                ),
                dependencies=["symbols"],
            )
        )

        # Phase 3: Complexity (depends on both calls and types)
        dag.add_node(
            DAGNode(
                id="complexity",
                execute=lambda wid, results: workflow.execute_activity(
                    analyze_complexity,
                    args=[wid, results["calls"], results["types"]],
                    start_to_close_timeout=timedelta(seconds=10),
                ),
                dependencies=["calls", "types"],
            )
        )

        # Execute DAG
        results = await dag.execute(workspace_id=workspace_id)

        return {
            "workspace_id": workspace_id,
            "phases_completed": list(results.keys()),
            "final_result": results["complexity"],
        }


async def main():
    """Test DAG workflow"""
    print("🧪 Testing VelvetEcho DAG Pattern...")
    print()

    # Connect
    print("1️⃣  Connecting to Temporal...")
    client = await Client.connect("localhost:7233")
    print("   ✅ Connected")
    print()

    task_queue = "velvetecho-dag-test"

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
        print("      Phase 1: symbols")
        print("      Phase 2: calls, types (parallel)")
        print("      Phase 3: complexity (final)")
        print()

        handle = await client.start_workflow(
            AnalysisDAGWorkflow.run,
            "workspace-123",
            id="dag-test-001",
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
        print(f"      Phases: {result['phases_completed']}")
        print(f"      Final: {result['final_result']}")
        print()

    print("✅ DAG Pattern test PASSED!")
    print()
    print("VelvetEcho's core workflow pattern is working! 🎉")


if __name__ == "__main__":
    asyncio.run(main())
