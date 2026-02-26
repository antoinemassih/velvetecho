"""Command and Query buses for dispatching"""

from typing import Dict, Type, Any, TypeVar
import structlog

from velvetecho.cqrs.command import Command, CommandHandler
from velvetecho.cqrs.query import Query, QueryHandler

logger = structlog.get_logger(__name__)

TCommand = TypeVar("TCommand", bound=Command)
TQuery = TypeVar("TQuery", bound=Query)


class CommandBus:
    """
    Command bus for dispatching commands to handlers.

    Example:
        bus = CommandBus()

        # Register handler
        bus.register(CreateWorkspaceCommand, CreateWorkspaceHandler(repo))

        # Dispatch command
        command = CreateWorkspaceCommand(name="test", description="...")
        result = await bus.dispatch(command)
    """

    def __init__(self):
        self._handlers: Dict[Type[Command], CommandHandler] = {}

    def register(self, command_type: Type[TCommand], handler: CommandHandler) -> None:
        """Register a command handler"""
        self._handlers[command_type] = handler
        logger.info(
            "Registered command handler",
            command=command_type.__name__,
            handler=handler.__class__.__name__,
        )

    async def dispatch(self, command: TCommand) -> Any:
        """Dispatch command to its handler"""
        command_type = type(command)

        if command_type not in self._handlers:
            raise ValueError(f"No handler registered for command: {command_type.__name__}")

        handler = self._handlers[command_type]

        logger.info(
            "Dispatching command",
            command=command_type.__name__,
            handler=handler.__class__.__name__,
        )

        try:
            result = await handler.handle(command)
            logger.info("Command handled successfully", command=command_type.__name__)
            return result
        except Exception as e:
            logger.error(
                "Command handling failed",
                command=command_type.__name__,
                error=str(e),
                exc_info=True,
            )
            raise


class QueryBus:
    """
    Query bus for dispatching queries to handlers.

    Example:
        bus = QueryBus()

        # Register handler
        bus.register(GetWorkspaceQuery, GetWorkspaceHandler(repo))

        # Dispatch query
        query = GetWorkspaceQuery(workspace_id="123")
        result = await bus.dispatch(query)
    """

    def __init__(self):
        self._handlers: Dict[Type[Query], QueryHandler] = {}

    def register(self, query_type: Type[TQuery], handler: QueryHandler) -> None:
        """Register a query handler"""
        self._handlers[query_type] = handler
        logger.info(
            "Registered query handler",
            query=query_type.__name__,
            handler=handler.__class__.__name__,
        )

    async def dispatch(self, query: TQuery) -> Any:
        """Dispatch query to its handler"""
        query_type = type(query)

        if query_type not in self._handlers:
            raise ValueError(f"No handler registered for query: {query_type.__name__}")

        handler = self._handlers[query_type]

        logger.debug(
            "Dispatching query",
            query=query_type.__name__,
            handler=handler.__class__.__name__,
        )

        try:
            result = await handler.handle(query)
            logger.debug("Query handled successfully", query=query_type.__name__)
            return result
        except Exception as e:
            logger.error(
                "Query handling failed",
                query=query_type.__name__,
                error=str(e),
                exc_info=True,
            )
            raise
