"""Multi-service orchestration patterns for complex workflows"""

from typing import Optional, Dict, Any, List
from velvetecho.tasks import activity
from velvetecho.communication import RPCClient
import structlog

logger = structlog.get_logger(__name__)


class ServiceOrchestrator:
    """
    Helper for orchestrating multi-service workflows.

    Provides convenience methods for common patterns:
    - Session-based agent calls
    - Tool execution
    - Fan-out/fan-in

    Example:
        orchestrator = ServiceOrchestrator(rpc_client)

        # Start session
        session_id = await orchestrator.start_session("code-analyst")

        # Send message to agent
        result = await orchestrator.agent_message(session_id, "Analyze this")

        # Execute tool via session
        tool_result = await orchestrator.execute_tool(session_id, "read_file", {...})

        # Fan-out to multiple agents
        results = await orchestrator.fan_out_agents(session_id, [
            "Analyze aspect 1",
            "Analyze aspect 2",
            "Analyze aspect 3",
        ])
    """

    def __init__(self, rpc_client: RPCClient):
        self.rpc = rpc_client

    async def start_session(
        self,
        agent_id: str,
        context: Optional[Dict[str, Any]] = None,
        service: str = "lobsterclaws"
    ) -> str:
        """
        Start an agent session.

        Args:
            agent_id: Agent identifier
            context: Initial context
            service: Service name (default: lobsterclaws)

        Returns:
            session_id
        """
        result = await self.rpc.call(
            service=service,
            method="create_session",
            params={
                "agent_id": agent_id,
                "context": context or {}
            }
        )

        session_id = result["session_id"]

        logger.info(
            "Started agent session",
            agent_id=agent_id,
            session_id=session_id
        )

        return session_id

    async def agent_message(
        self,
        session_id: str,
        message: str,
        timeout: int = 180,
        service: str = "lobsterclaws"
    ) -> Dict[str, Any]:
        """
        Send message to agent via session.

        Args:
            session_id: Session identifier
            message: Message to send
            timeout: Timeout in seconds (default: 180)
            service: Service name (default: lobsterclaws)

        Returns:
            Agent response
        """
        result = await self.rpc.call(
            service=service,
            method="send_message",
            params={
                "session_id": session_id,
                "message": message
            },
            timeout=timeout
        )

        logger.info(
            "Agent responded",
            session_id=session_id,
            message_length=len(message)
        )

        return result

    async def execute_tool(
        self,
        session_id: str,
        tool: str,
        args: Dict[str, Any],
        service: str = "lobsterclaws"
    ) -> Dict[str, Any]:
        """
        Execute tool via session.

        Args:
            session_id: Session identifier
            tool: Tool name
            args: Tool arguments
            service: Service name (default: lobsterclaws)

        Returns:
            Tool result
        """
        result = await self.rpc.call(
            service=service,
            method="execute_tool",
            params={
                "session_id": session_id,
                "tool": tool,
                "args": args
            }
        )

        logger.info(
            "Tool executed",
            session_id=session_id,
            tool=tool
        )

        return result

    async def fan_out_agents(
        self,
        session_id: str,
        messages: List[str],
        timeout: int = 180,
        service: str = "lobsterclaws"
    ) -> List[Dict[str, Any]]:
        """
        Send multiple messages to agent in parallel.

        Args:
            session_id: Session identifier
            messages: List of messages to send
            timeout: Timeout per message
            service: Service name

        Returns:
            List of agent responses (in same order as messages)
        """
        import asyncio

        tasks = [
            self.agent_message(session_id, msg, timeout, service)
            for msg in messages
        ]

        results = await asyncio.gather(*tasks)

        logger.info(
            "Fan-out completed",
            session_id=session_id,
            count=len(messages)
        )

        return results

    async def close_session(
        self,
        session_id: str,
        service: str = "lobsterclaws"
    ) -> None:
        """Close an agent session"""
        await self.rpc.call(
            service=service,
            method="close_session",
            params={"session_id": session_id}
        )

        logger.info("Closed session", session_id=session_id)


def create_session_activity(orchestrator: ServiceOrchestrator):
    """
    Create activity for starting sessions.

    Example:
        orchestrator = ServiceOrchestrator(rpc)
        start_session = create_session_activity(orchestrator)

        @workflow
        async def my_workflow():
            session_id = await start_session.run("code-analyst", {"task": "..."})
    """
    @activity(start_to_close_timeout=30)
    async def start_session_activity(agent_id: str, context: Dict[str, Any]) -> str:
        return await orchestrator.start_session(agent_id, context)

    return start_session_activity


def create_agent_message_activity(orchestrator: ServiceOrchestrator):
    """
    Create activity for sending agent messages.

    Example:
        send_message = create_agent_message_activity(orchestrator)

        @workflow
        async def my_workflow(session_id: str):
            result = await send_message.run(session_id, "Analyze this")
    """
    @activity(start_to_close_timeout=180)
    async def agent_message_activity(session_id: str, message: str) -> Dict[str, Any]:
        return await orchestrator.agent_message(session_id, message)

    return agent_message_activity


def create_tool_activity(orchestrator: ServiceOrchestrator):
    """
    Create activity for executing tools.

    Example:
        execute_tool = create_tool_activity(orchestrator)

        @workflow
        async def my_workflow(session_id: str):
            result = await execute_tool.run(session_id, "read_file", {"path": "..."})
    """
    @activity(start_to_close_timeout=60)
    async def tool_activity(session_id: str, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return await orchestrator.execute_tool(session_id, tool, args)

    return tool_activity
