"""Simple integration test to verify VelvetEcho + Temporal works"""

import asyncio
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker


# Define a simple activity
@activity.defn
async def say_hello(name: str) -> str:
    """Simple activity that returns a greeting"""
    return f"Hello, {name}!"


# Define a simple workflow (class-based, as Temporal requires)
@workflow.defn
class HelloWorkflow:
    """Simple workflow that calls the hello activity"""

    @workflow.run
    async def run(self, name: str) -> str:
        """Run the workflow"""
        result = await workflow.execute_activity(
            say_hello,
            name,
            start_to_close_timeout=timedelta(seconds=10),
        )
        return result


async def main():
    """Test the integration"""
    print("🧪 Testing VelvetEcho + Temporal Integration...")
    print()

    # Connect to Temporal
    print("1️⃣  Connecting to Temporal...")
    client = await Client.connect("localhost:7233")
    print("   ✅ Connected to Temporal server")
    print()

    # Create worker
    print("2️⃣  Starting worker...")
    task_queue = "velvetecho-test"

    # Start worker in background
    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[HelloWorkflow],
        activities=[say_hello],
    ):
        print(f"   ✅ Worker started on task queue: {task_queue}")
        print()

        # Execute workflow
        print("3️⃣  Executing workflow...")
        handle = await client.start_workflow(
            HelloWorkflow.run,
            "VelvetEcho",
            id="test-workflow-001",
            task_queue=task_queue,
        )
        print(f"   ✅ Workflow started: {handle.id}")
        print()

        # Wait for result
        print("4️⃣  Waiting for result...")
        result = await handle.result()
        print(f"   ✅ Workflow completed!")
        print(f"   📝 Result: {result}")
        print()

    print("✅ Integration test PASSED!")
    print()
    print("VelvetEcho infrastructure is working correctly! 🎉")


if __name__ == "__main__":
    asyncio.run(main())
