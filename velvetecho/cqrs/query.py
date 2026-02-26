"""Query pattern (read operations)"""

from typing import Generic, TypeVar, Any
from abc import ABC, abstractmethod
from pydantic import BaseModel

TQuery = TypeVar("TQuery", bound="Query")
TResult = TypeVar("TResult")


class Query(BaseModel):
    """
    Base class for queries (read operations).

    Queries retrieve data without side effects.

    Example:
        class GetWorkspaceQuery(Query):
            workspace_id: str

        class ListWorkspacesQuery(Query):
            page: int = 1
            limit: int = 10
            search: Optional[str] = None
    """

    pass


class QueryHandler(ABC, Generic[TQuery, TResult]):
    """
    Base class for query handlers.

    Handlers execute queries and return results.

    Example:
        class GetWorkspaceHandler(QueryHandler[GetWorkspaceQuery, Workspace]):
            def __init__(self, repository: WorkspaceRepository):
                self.repository = repository

            async def handle(self, query: GetWorkspaceQuery) -> Workspace:
                workspace = await self.repository.get_by_id(query.workspace_id)
                if not workspace:
                    raise NotFoundException("Workspace", query.workspace_id)
                return workspace
    """

    @abstractmethod
    async def handle(self, query: TQuery) -> TResult:
        """Handle the query and return result"""
        pass
