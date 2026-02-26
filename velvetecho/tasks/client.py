"""Temporal client wrapper"""

from typing import Optional, Any
from temporalio.client import Client, WorkflowHandle
from temporalio.common import RetryPolicy
import structlog

from velvetecho.config import get_config, VelvetEchoConfig

logger = structlog.get_logger(__name__)


class TemporalClient:
    """
    Wrapper for Temporal client with VelvetEcho configuration.

    Handles workflow execution, querying, and management.
    """

    def __init__(self, config: Optional[VelvetEchoConfig] = None):
        self.config = config or get_config()
        self._client: Optional[Client] = None

    async def connect(self) -> None:
        """Connect to Temporal server"""
        if self._client is not None:
            return

        logger.info(
            "Connecting to Temporal",
            host=self.config.temporal_host,
            namespace=self.config.temporal_namespace,
        )

        self._client = await Client.connect(
            self.config.temporal_host,
            namespace=self.config.temporal_namespace,
        )

        logger.info("Connected to Temporal successfully")

    async def disconnect(self) -> None:
        """Disconnect from Temporal server"""
        if self._client is not None:
            await self._client.close()
            self._client = None
            logger.info("Disconnected from Temporal")

    @property
    def client(self) -> Client:
        """Get underlying Temporal client"""
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")
        return self._client

    async def start_workflow(
        self,
        workflow: Any,
        *args: Any,
        workflow_id: Optional[str] = None,
        task_queue: Optional[str] = None,
        execution_timeout: Optional[int] = None,
        run_timeout: Optional[int] = None,
        retry_policy: Optional[dict] = None,
        **kwargs: Any,
    ) -> WorkflowHandle:
        """
        Start a workflow execution.

        Args:
            workflow: Workflow function (decorated with @workflow)
            *args: Positional arguments for workflow
            workflow_id: Unique workflow ID (auto-generated if None)
            task_queue: Task queue name (defaults to service queue)
            execution_timeout: Total execution timeout (seconds)
            run_timeout: Single run timeout (seconds)
            retry_policy: Retry policy dict
            **kwargs: Keyword arguments for workflow

        Returns:
            WorkflowHandle for querying and interacting with workflow
        """
        if self._client is None:
            await self.connect()

        # Get workflow config if available
        workflow_config = getattr(workflow, "_velvetecho_config", None)

        # Build retry policy
        retry = None
        if retry_policy or (workflow_config and workflow_config.retry_policy):
            retry_dict = retry_policy or workflow_config.retry_policy
            retry = RetryPolicy(
                maximum_attempts=retry_dict.get("max_attempts"),
                backoff_coefficient=retry_dict.get("backoff_coefficient", 2.0),
                initial_interval=retry_dict.get("initial_interval", 1),
                maximum_interval=retry_dict.get("max_interval", 100),
            )

        handle = await self.client.start_workflow(
            workflow._temporal_workflow if hasattr(workflow, "_temporal_workflow") else workflow,
            *args,
            id=workflow_id,
            task_queue=task_queue or self.config.task_queue,
            execution_timeout=execution_timeout,
            run_timeout=run_timeout,
            retry_policy=retry,
            **kwargs,
        )

        logger.info(
            "Started workflow",
            workflow_id=handle.id,
            workflow_name=workflow_config.name if workflow_config else workflow.__name__,
        )

        return handle

    async def get_workflow_handle(
        self,
        workflow_id: str,
        run_id: Optional[str] = None,
    ) -> WorkflowHandle:
        """Get handle for existing workflow"""
        if self._client is None:
            await self.connect()

        return self.client.get_workflow_handle(workflow_id, run_id=run_id)

    async def query_workflow(
        self,
        workflow_id: str,
        query_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Query a running workflow"""
        handle = await self.get_workflow_handle(workflow_id)
        return await handle.query(query_name, *args, **kwargs)

    async def signal_workflow(
        self,
        workflow_id: str,
        signal_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Send signal to a running workflow"""
        handle = await self.get_workflow_handle(workflow_id)
        await handle.signal(signal_name, *args, **kwargs)

    async def cancel_workflow(self, workflow_id: str) -> None:
        """Cancel a running workflow"""
        handle = await self.get_workflow_handle(workflow_id)
        await handle.cancel()
        logger.info("Cancelled workflow", workflow_id=workflow_id)

    async def terminate_workflow(
        self,
        workflow_id: str,
        reason: str = "Terminated by client",
    ) -> None:
        """Terminate a running workflow"""
        handle = await self.get_workflow_handle(workflow_id)
        await handle.terminate(reason)
        logger.info("Terminated workflow", workflow_id=workflow_id, reason=reason)


# Global client instance
_client: Optional[TemporalClient] = None


def init_client(config: Optional[VelvetEchoConfig] = None) -> TemporalClient:
    """Initialize global client instance"""
    global _client
    _client = TemporalClient(config)
    return _client


def get_client() -> TemporalClient:
    """Get global client instance"""
    if _client is None:
        raise RuntimeError(
            "Temporal client not initialized. Call init_client() first."
        )
    return _client
