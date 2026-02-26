"""Batch execution pattern for parallel task processing with concurrency control"""

import asyncio
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass


@dataclass
class BatchResult:
    """Result of batch execution"""

    total: int
    succeeded: int
    failed: int
    results: List[Any]
    errors: List[Dict[str, Any]]


class BatchWorkflow:
    """
    Helper for executing tasks in parallel batches with concurrency control.

    Features:
    - Chunked execution (respects max_parallelism)
    - Automatic error handling
    - Progress tracking
    - Result aggregation

    Example:
        @workflow
        async def process_files(file_paths: List[str]):
            batch = BatchWorkflow(max_parallelism=10)

            results = await batch.execute(
                items=file_paths,
                task_fn=process_file.run,
                task_args={"workspace_id": workspace_id},
            )

            return {
                "total": results.total,
                "succeeded": results.succeeded,
                "failed": results.failed,
            }
    """

    def __init__(self, max_parallelism: int = 10):
        self.max_parallelism = max_parallelism

    async def execute(
        self,
        items: List[Any],
        task_fn: Callable,
        task_args: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BatchResult:
        """
        Execute tasks in parallel batches.

        Args:
            items: List of items to process
            task_fn: Activity function to call for each item
            task_args: Additional arguments to pass to task_fn
            progress_callback: Optional callback(completed, total)

        Returns:
            BatchResult with aggregated results
        """
        task_args = task_args or {}
        results = []
        errors = []
        succeeded = 0
        failed = 0
        total = len(items)

        # Execute in chunks
        for i in range(0, len(items), self.max_parallelism):
            chunk = items[i : i + self.max_parallelism]

            # Create tasks for chunk
            tasks = [
                task_fn(item=item, **task_args)
                for item in chunk
            ]

            # Execute chunk
            chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for idx, result in enumerate(chunk_results):
                if isinstance(result, Exception):
                    failed += 1
                    errors.append({
                        "item": chunk[idx],
                        "error": str(result),
                        "type": type(result).__name__,
                    })
                    results.append(None)
                else:
                    succeeded += 1
                    results.append(result)

            # Progress callback
            if progress_callback:
                progress_callback(succeeded + failed, total)

        return BatchResult(
            total=total,
            succeeded=succeeded,
            failed=failed,
            results=results,
            errors=errors,
        )
