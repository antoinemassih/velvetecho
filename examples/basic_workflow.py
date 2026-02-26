"""
Basic workflow example showing core VelvetEcho patterns.

This example demonstrates:
- Configuration setup
- Activity definition with retries
- Workflow orchestration
- Worker execution
- Client-side workflow triggering
"""

import asyncio
import httpx
from velvetecho.config import VelvetEchoConfig, init_config
from velvetecho.tasks import workflow, activity, WorkerManager, get_client, init_client


# 1. Configure VelvetEcho
config = VelvetEchoConfig(
    service_name="example-service",
    temporal_host="localhost:7233",
    temporal_namespace="default",
    redis_url="redis://localhost:6379/0",
)
init_config(config)


# 2. Define Activities (units of work)
@activity(
    start_to_close_timeout=60,
    retry_policy={"max_attempts": 3, "initial_interval": 1, "backoff_coefficient": 2.0},
)
async def fetch_user_data(user_id: str) -> dict:
    """Fetch user data from API"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://jsonplaceholder.typicode.com/users/{user_id}")
        return response.json()


@activity(start_to_close_timeout=30)
async def fetch_user_posts(user_id: str) -> list:
    """Fetch user's posts"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://jsonplaceholder.typicode.com/posts?userId={user_id}"
        )
        return response.json()


@activity(start_to_close_timeout=30)
async def enrich_user_data(user_data: dict, posts: list) -> dict:
    """Combine user data with their posts"""
    return {
        **user_data,
        "posts": posts,
        "post_count": len(posts),
    }


# 3. Define Workflow (orchestration)
@workflow(execution_timeout=300)
async def process_user(user_id: str) -> dict:
    """
    Process a user by fetching their data and posts, then enriching.

    This workflow:
    1. Fetches user data
    2. Fetches user posts (can retry independently)
    3. Enriches data with posts
    """
    # Execute activities
    user_data = await fetch_user_data.run(user_id)
    posts = await fetch_user_posts.run(user_id)
    enriched = await enrich_user_data.run(user_data, posts)

    return enriched


# 4. Worker (executes workflows and activities)
async def run_worker_example():
    """Start a worker to execute workflows and activities"""
    worker = WorkerManager(
        config=config,
        workflows=[process_user],
        activities=[fetch_user_data, fetch_user_posts, enrich_user_data],
    )

    print(f"Worker starting on task queue: {config.task_queue}")
    print("Waiting for workflows to execute...")
    await worker.start()


# 5. Client (triggers workflows)
async def trigger_workflow_example():
    """Trigger a workflow from a client"""
    # Initialize client
    client = init_client(config)
    await client.connect()

    # Start workflow
    print("Starting workflow for user 1...")
    handle = await client.start_workflow(process_user, "1", workflow_id="process-user-1")

    print(f"Workflow started: {handle.id}")
    print("Waiting for result...")

    # Wait for result
    result = await handle.result()
    print(f"Workflow completed!")
    print(f"User: {result['name']}")
    print(f"Email: {result['email']}")
    print(f"Posts: {result['post_count']}")

    await client.disconnect()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python basic_workflow.py worker   # Start worker")
        print("  python basic_workflow.py client   # Trigger workflow")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "worker":
        asyncio.run(run_worker_example())
    elif mode == "client":
        asyncio.run(trigger_workflow_example())
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
