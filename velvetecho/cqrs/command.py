"""Command pattern (write operations)"""

from typing import Generic, TypeVar, Any
from abc import ABC, abstractmethod
from pydantic import BaseModel

TCommand = TypeVar("TCommand", bound="Command")
TResult = TypeVar("TResult")


class Command(BaseModel):
    """
    Base class for commands (write operations).

    Commands represent intent to change state.

    Example:
        class CreateWorkspaceCommand(Command):
            name: str
            description: str
            created_by: str
    """

    pass


class CommandHandler(ABC, Generic[TCommand, TResult]):
    """
    Base class for command handlers.

    Handlers process commands and execute business logic.

    Example:
        class CreateWorkspaceHandler(CommandHandler[CreateWorkspaceCommand, Workspace]):
            def __init__(self, repository: WorkspaceRepository):
                self.repository = repository

            async def handle(self, command: CreateWorkspaceCommand) -> Workspace:
                workspace = Workspace(
                    name=command.name,
                    description=command.description,
                    created_by=command.created_by,
                )
                return await self.repository.create(workspace)
    """

    @abstractmethod
    async def handle(self, command: TCommand) -> TResult:
        """Handle the command and return result"""
        pass
