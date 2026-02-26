"""CQRS (Command Query Responsibility Segregation) pattern"""

from velvetecho.cqrs.command import Command, CommandHandler
from velvetecho.cqrs.query import Query, QueryHandler
from velvetecho.cqrs.bus import CommandBus, QueryBus
from velvetecho.cqrs.decorators import command_handler, query_handler

__all__ = [
    "Command",
    "CommandHandler",
    "Query",
    "QueryHandler",
    "CommandBus",
    "QueryBus",
    "command_handler",
    "query_handler",
]
