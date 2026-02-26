"""
Example showing parallel activity execution.

Demonstrates how to run multiple activities concurrently for improved performance.
"""

import asyncio
from velvetecho.config import VelvetEchoConfig, init_config
from velvetecho.tasks import workflow, activity
from temporalio import workflow as temporal_workflow


config = VelvetEchoConfig(service_name="parallel-example")
init_config(config)


@activity(start_to_close_timeout=60)
async def analyze_file(file_path: str) -> dict:
    """Analyze a single file (simulated)"""
    await asyncio.sleep(2)  # Simulate work
    return {"file": file_path, "lines": 100, "complexity": 5}


@workflow
async def analyze_project(file_paths: list[str]) -> dict:
    """
    Analyze multiple files in parallel.

    Instead of running sequentially (slow):
        results = []
        for path in file_paths:
            result = await analyze_file.run(path)
            results.append(result)

    Run in parallel (fast):
        tasks = [analyze_file.run(path) for path in file_paths]
        results = await asyncio.gather(*tasks)
    """
    # Execute all file analyses in parallel
    tasks = [analyze_file.run(path) for path in file_paths]
    results = await asyncio.gather(*tasks)

    # Aggregate results
    total_lines = sum(r["lines"] for r in results)
    avg_complexity = sum(r["complexity"] for r in results) / len(results)

    return {
        "files_analyzed": len(results),
        "total_lines": total_lines,
        "avg_complexity": avg_complexity,
        "files": results,
    }
