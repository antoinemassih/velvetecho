"""Temporal worker management"""

from typing import Optional, List, Any
from temporalio.client import Client
from temporalio.worker import Worker
import structlog

from velvetecho.config import get_config, VelvetEchoConfig

logger = structlog.get_logger(__name__)


class WorkerManager:
    """
    Manages Temporal workers for activity and workflow execution.

    Workers poll task queues and execute activities/workflows registered with them.
    """

    def __init__(
        self,
        config: Optional[VelvetEchoConfig] = None,
        workflows: Optional[List[Any]] = None,
        activities: Optional[List[Any]] = None,
        task_queue: Optional[str] = None,
    ):
        self.config = config or get_config()
        self.workflows = workflows or []
        self.activities = activities or []
        self.task_queue = task_queue or self.config.task_queue
        self._client: Optional[Client] = None
        self._worker: Optional[Worker] = None

    async def connect(self) -> None:
        """Connect to Temporal server"""
        if self._client is not None:
            return

        logger.info(
            "Connecting worker to Temporal",
            host=self.config.temporal_host,
            namespace=self.config.temporal_namespace,
            task_queue=self.task_queue,
        )

        self._client = await Client.connect(
            self.config.temporal_host,
            namespace=self.config.temporal_namespace,
        )

        logger.info("Worker connected to Temporal")

    def register_workflow(self, workflow: Any) -> None:
        """Register a workflow with this worker"""
        # Extract temporal workflow if wrapped
        if hasattr(workflow, "_temporal_workflow"):
            workflow = workflow._temporal_workflow

        if workflow not in self.workflows:
            self.workflows.append(workflow)
            logger.debug("Registered workflow", workflow=workflow.__name__)

    def register_activity(self, activity: Any) -> None:
        """Register an activity with this worker"""
        # Extract temporal activity if wrapped
        if hasattr(activity, "_temporal_activity"):
            activity = activity._temporal_activity

        if activity not in self.activities:
            self.activities.append(activity)
            logger.debug("Registered activity", activity=activity.__name__)

    async def start(self) -> None:
        """Start the worker (blocks until stopped)"""
        if self._client is None:
            await self.connect()

        if not self.workflows and not self.activities:
            raise RuntimeError(
                "No workflows or activities registered. "
                "Call register_workflow() or register_activity() first."
            )

        logger.info(
            "Starting worker",
            task_queue=self.task_queue,
            workflows=len(self.workflows),
            activities=len(self.activities),
            max_concurrent_activities=self.config.temporal_max_concurrent_activities,
        )

        self._worker = Worker(
            self._client,
            task_queue=self.task_queue,
            workflows=self.workflows,
            activities=self.activities,
            max_concurrent_activities=self.config.temporal_max_concurrent_activities,
        )

        logger.info("Worker started successfully")
        await self._worker.run()

    async def stop(self) -> None:
        """Stop the worker gracefully"""
        if self._worker is not None:
            logger.info("Stopping worker")
            await self._worker.shutdown()
            self._worker = None

        if self._client is not None:
            await self._client.close()
            self._client = None

        logger.info("Worker stopped")


async def run_worker(
    config: Optional[VelvetEchoConfig] = None,
    workflows: Optional[List[Any]] = None,
    activities: Optional[List[Any]] = None,
    task_queue: Optional[str] = None,
) -> None:
    """
    Convenience function to start a worker.

    Example:
        from velvetecho.tasks import run_worker

        workflows = [process_data, analyze_results]
        activities = [fetch_data, transform_data, save_result]

        await run_worker(workflows=workflows, activities=activities)
    """
    worker = WorkerManager(
        config=config,
        workflows=workflows,
        activities=activities,
        task_queue=task_queue,
    )
    await worker.start()
