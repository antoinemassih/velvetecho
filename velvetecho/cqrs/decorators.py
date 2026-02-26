"""Decorators for registering handlers"""

from typing import Type, Callable
from velvetecho.cqrs.command import Command, CommandHandler
from velvetecho.cqrs.query import Query, QueryHandler


def command_handler(command_type: Type[Command]):
    """
    Decorator to mark a class as a command handler.

    Example:
        @command_handler(CreateWorkspaceCommand)
        class CreateWorkspaceHandler(CommandHandler):
            async def handle(self, command: CreateWorkspaceCommand):
                ...
    """

    def decorator(handler_class):
        handler_class._command_type = command_type
        return handler_class

    return decorator


def query_handler(query_type: Type[Query]):
    """
    Decorator to mark a class as a query handler.

    Example:
        @query_handler(GetWorkspaceQuery)
        class GetWorkspaceHandler(QueryHandler):
            async def handle(self, query: GetWorkspaceQuery):
                ...
    """

    def decorator(handler_class):
        handler_class._query_type = query_type
        return handler_class

    return decorator
