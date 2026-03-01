"""Enterprise Workflow Tests

Tests that require Temporal workflows:
1. Load Testing - 20 concurrent workflows
2. Stress Testing - 51-node DAG
3. Concurrent DAG Execution - 15 parallel DAGs
"""

import asyncio
import time
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker


print("=" * 80)
print("🏢 VELVETECHO ENTERPRISE WORKFLOW TESTS")
print("=" * 80)
print()

test_results = {}


# ============================================================================
# TEST 1: Load Testing - Concurrent Workflows
# ============================================================================
@activity.defn
async def compute_task(task_id: int) -> dict:
    """Simulates computation"""
    await asyncio.sleep(0.05)
    return {"task_id": task_id, "result": task_id ** 2}


@workflow.defn
class LoadTestWorkflow:
    """Simple workflow for load testing"""

    @workflow.run
    async def run(self, task_id: int, task_count: int = 5) -> dict:
        start = workflow.now().timestamp()

        results = []
        for i in range(task_count):
            result = await workflow.execute_activity(
                compute_task,
                task_id * 100 + i,
                start_to_close_timeout=timedelta(seconds=10),
            )
            results.append(result)

        elapsed = workflow.now().timestamp() - start
        return {
            "task_id": task_id,
            "task_count": task_count,
            "results": results,
            "elapsed": elapsed,
        }


async def test_load_concurrent_workflows():
    """Test multiple concurrent workflow executions"""
    print("📋 TEST 1: Load Testing - 20 Concurrent Workflows")
    print("-" * 80)

    try:
        client = await Client.connect("localhost:7233")
        task_queue = "enterprise-load-test"

        num_workflows = 20
        task_count_per_workflow = 5

        print(f"   Starting worker...")

        async with Worker(
            client,
            task_queue=task_queue,
            workflows=[LoadTestWorkflow],
            activities=[compute_task],
            max_concurrent_workflow_tasks=50,
            max_concurrent_activities=100,
        ):
            print(f"   Launching {num_workflows} workflows...")
            start_time = time.time()

            handles = []
            for i in range(num_workflows):
                handle = await client.start_workflow(
                    LoadTestWorkflow.run,
                    args=[i, task_count_per_workflow],
                    id=f"load-test-{i}-{time.time()}",
                    task_queue=task_queue,
                )
                handles.append(handle)

            print(f"   ✅ Launched {num_workflows} workflows")
            print(f"   Waiting for completion...")

            results = await asyncio.gather(*[h.result() for h in handles])

            total_time = time.time() - start_time
            total_tasks = num_workflows * task_count_per_workflow

            print(f"   ✅ All workflows completed!")
            print(f"   Total time: {total_time:.2f}s")
            print(f"   Total tasks: {total_tasks}")
            print(f"   Throughput: {total_tasks/total_time:.2f} tasks/sec")
            print(f"   Avg workflow time: {sum(r['elapsed'] for r in results)/len(results):.2f}s")

            test_results["load_testing"] = {
                "status": "passed",
                "num_workflows": num_workflows,
                "total_tasks": total_tasks,
                "total_time": total_time,
                "throughput": total_tasks / total_time,
            }

            print("   ✅ Load test PASSED")
            return True

    except Exception as e:
        print(f"   ❌ Load test FAILED: {e}")
        test_results["load_testing"] = {"status": "failed", "error": str(e)}
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 2: Stress Testing - Large DAG
# ============================================================================
@activity.defn
async def stress_activity(node_id: str) -> dict:
    """Activity for stress testing"""
    await asyncio.sleep(0.01)
    return {"node_id": node_id, "processed": True}


@workflow.defn
class StressDAGWorkflow:
    """Workflow with many nodes"""

    @workflow.run
    async def run(self) -> dict:
        # Import DAG here to avoid sandbox issues
        from velvetecho.patterns import DAGWorkflow, DAGNode

        dag = DAGWorkflow()

        # Layer 1: 10 independent nodes
        layer1_nodes = []
        for i in range(10):
            node_id = f"layer1_{i}"
            layer1_nodes.append(node_id)

            async def make_exec(nid):
                async def execute_layer1(dependencies, **kwargs):
                    return await workflow.execute_activity(
                        stress_activity,
                        nid,
                        start_to_close_timeout=timedelta(seconds=10),
                    )
                return execute_layer1

            dag.add_node(DAGNode(id=node_id, execute=await make_exec(node_id), dependencies=[]))

        # Layer 2: 20 nodes depending on Layer 1
        layer2_nodes = []
        for i in range(20):
            node_id = f"layer2_{i}"
            layer2_nodes.append(node_id)
            deps = [layer1_nodes[i % 10]]

            async def make_exec2(nid):
                async def execute_layer2(dependencies, **kwargs):
                    return await workflow.execute_activity(
                        stress_activity,
                        nid,
                        start_to_close_timeout=timedelta(seconds=10),
                    )
                return execute_layer2

            dag.add_node(DAGNode(id=node_id, execute=await make_exec2(node_id), dependencies=deps))

        # Layer 3: 20 nodes depending on Layer 2
        layer3_nodes = []
        for i in range(20):
            node_id = f"layer3_{i}"
            layer3_nodes.append(node_id)
            deps = [layer2_nodes[i % 20]]

            async def make_exec3(nid):
                async def execute_layer3(dependencies, **kwargs):
                    return await workflow.execute_activity(
                        stress_activity,
                        nid,
                        start_to_close_timeout=timedelta(seconds=10),
                    )
                return execute_layer3

            dag.add_node(DAGNode(id=node_id, execute=await make_exec3(node_id), dependencies=deps))

        # Final node
        async def execute_final(dependencies, **kwargs):
            return await workflow.execute_activity(
                stress_activity,
                "final",
                start_to_close_timeout=timedelta(seconds=10),
            )

        dag.add_node(DAGNode(id="final", execute=execute_final, dependencies=layer3_nodes))

        # Execute
        start = workflow.now().timestamp()
        results = await dag.execute()
        elapsed = workflow.now().timestamp() - start

        return {
            "total_nodes": len(results),
            "execution_time": elapsed,
            "nodes_per_second": len(results) / elapsed if elapsed > 0 else 0,
        }


async def test_stress_large_dag():
    """Test DAG with 51 nodes"""
    print()
    print("📋 TEST 2: Stress Testing - 51-Node DAG")
    print("-" * 80)

    try:
        client = await Client.connect("localhost:7233")
        task_queue = "enterprise-stress-test"

        print("   Starting worker...")

        async with Worker(
            client,
            task_queue=task_queue,
            workflows=[StressDAGWorkflow],
            activities=[stress_activity],
            max_concurrent_activities=100,
        ):
            print("   Executing 51-node DAG...")
            start_time = time.time()

            handle = await client.start_workflow(
                StressDAGWorkflow.run,
                id=f"stress-dag-{time.time()}",
                task_queue=task_queue,
            )

            result = await handle.result()
            total_time = time.time() - start_time

            print(f"   ✅ DAG completed!")
            print(f"   Total nodes: {result['total_nodes']}")
            print(f"   Execution time: {result['execution_time']:.2f}s")
            print(f"   Throughput: {result['nodes_per_second']:.2f} nodes/sec")
            print(f"   Wall clock: {total_time:.2f}s")

            assert result['total_nodes'] == 51

            test_results["stress_testing"] = {
                "status": "passed",
                "total_nodes": result['total_nodes'],
                "execution_time": result['execution_time'],
                "throughput": result['nodes_per_second'],
            }

            print("   ✅ Stress test PASSED")
            return True

    except Exception as e:
        print(f"   ❌ Stress test FAILED: {e}")
        test_results["stress_testing"] = {"status": "failed", "error": str(e)}
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# TEST 3: Concurrent DAG Execution
# ============================================================================
@activity.defn
async def concurrent_dag_activity(data: str) -> dict:
    """Activity for concurrent DAG testing"""
    await asyncio.sleep(0.05)
    return {"processed": data}


@workflow.defn
class ConcurrentDAGWorkflow:
    """Small DAG for concurrent testing"""

    @workflow.run
    async def run(self, workflow_id: int) -> dict:
        from velvetecho.patterns import DAGWorkflow, DAGNode

        dag = DAGWorkflow()

        # Simple 3-node DAG
        async def exec_a(dependencies, **kwargs):
            return await workflow.execute_activity(
                concurrent_dag_activity,
                f"A-{workflow_id}",
                start_to_close_timeout=timedelta(seconds=10),
            )

        async def exec_b(dependencies, **kwargs):
            return await workflow.execute_activity(
                concurrent_dag_activity,
                f"B-{workflow_id}",
                start_to_close_timeout=timedelta(seconds=10),
            )

        async def exec_c(dependencies, **kwargs):
            return await workflow.execute_activity(
                concurrent_dag_activity,
                f"C-{workflow_id}",
                start_to_close_timeout=timedelta(seconds=10),
            )

        dag.add_node(DAGNode(id="a", execute=exec_a, dependencies=[]))
        dag.add_node(DAGNode(id="b", execute=exec_b, dependencies=["a"]))
        dag.add_node(DAGNode(id="c", execute=exec_c, dependencies=["a", "b"]))

        results = await dag.execute(workflow_id=workflow_id)

        return {"workflow_id": workflow_id, "nodes_completed": len(results)}


async def test_concurrent_dag_execution():
    """Test 15 DAG workflows running concurrently"""
    print()
    print("📋 TEST 3: Concurrent DAG Execution - 15 Parallel DAGs")
    print("-" * 80)

    try:
        client = await Client.connect("localhost:7233")
        task_queue = "enterprise-concurrent-dag"

        num_dags = 15
        print(f"   Starting worker...")

        async with Worker(
            client,
            task_queue=task_queue,
            workflows=[ConcurrentDAGWorkflow],
            activities=[concurrent_dag_activity],
            max_concurrent_workflow_tasks=50,
            max_concurrent_activities=100,
        ):
            print(f"   Launching {num_dags} DAG workflows...")
            start_time = time.time()

            handles = []
            for i in range(num_dags):
                handle = await client.start_workflow(
                    ConcurrentDAGWorkflow.run,
                    i,
                    id=f"concurrent-dag-{i}-{time.time()}",
                    task_queue=task_queue,
                )
                handles.append(handle)

            print(f"   ✅ Launched {num_dags} workflows")

            results = await asyncio.gather(*[h.result() for h in handles])

            total_time = time.time() - start_time

            print(f"   ✅ All DAGs completed!")
            print(f"   Total time: {total_time:.2f}s")
            print(f"   Avg time per DAG: {total_time/num_dags:.2f}s")
            print(f"   Total nodes: {sum(r['nodes_completed'] for r in results)}")

            assert all(r['nodes_completed'] == 3 for r in results)

            test_results["concurrent_dag"] = {
                "status": "passed",
                "num_dags": num_dags,
                "total_time": total_time,
                "total_nodes": sum(r['nodes_completed'] for r in results),
            }

            print("   ✅ Concurrent DAG test PASSED")
            return True

    except Exception as e:
        print(f"   ❌ Concurrent DAG test FAILED: {e}")
        test_results["concurrent_dag"] = {"status": "failed", "error": str(e)}
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# MAIN RUNNER
# ============================================================================
async def run_workflow_tests():
    """Run all workflow tests"""
    print()
    print("Starting enterprise workflow tests...")
    print("This may take several minutes...")
    print()

    await test_load_concurrent_workflows()
    await test_stress_large_dag()
    await test_concurrent_dag_execution()

    # Summary
    print()
    print("=" * 80)
    print("📊 WORKFLOW TEST SUMMARY")
    print("=" * 80)
    print()

    passed = sum(1 for v in test_results.values() if v.get("status") == "passed")
    total = len(test_results)

    for test_name, result in test_results.items():
        status = "✅" if result.get("status") == "passed" else "❌"
        print(f"   {status} {test_name.replace('_', ' ').title()}")

        if isinstance(result, dict):
            for key, value in result.items():
                if key not in ["status", "error"]:
                    if isinstance(value, float):
                        print(f"      • {key}: {value:.2f}")
                    else:
                        print(f"      • {key}: {value}")

    print()
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print()

    if passed == total:
        print("🎉 ALL WORKFLOW TESTS PASSED!")
        return True
    else:
        print("⚠️  Some tests failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_workflow_tests())
    exit(0 if success else 1)
