"""Pagination utilities"""

from typing import TypeVar, List, Generic
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class PaginationParams(BaseModel):
    """
    Pagination query parameters.

    Example:
        @app.get("/workspaces")
        async def list_workspaces(
            page: int = Query(1, ge=1),
            limit: int = Query(10, ge=1, le=100),
        ):
            params = PaginationParams(page=page, limit=limit)
            result = await paginate(session, select(Workspace), params)
    """

    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    limit: int = Field(10, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset from page and limit"""
        return (self.page - 1) * self.limit


class PaginatedResult(BaseModel, Generic[T]):
    """
    Paginated result container.

    Example:
        result = await paginate(session, select(Workspace), params)
        # result.items: List[Workspace]
        # result.total: int
        # result.page: int
        # result.limit: int
        # result.has_next: bool
        # result.has_prev: bool
    """

    items: List[T]
    total: int
    page: int
    limit: int
    has_next: bool
    has_prev: bool

    class Config:
        arbitrary_types_allowed = True


async def paginate(
    session: AsyncSession,
    stmt,  # SQLAlchemy select statement
    params: PaginationParams,
) -> PaginatedResult:
    """
    Paginate a SQLAlchemy query.

    Example:
        from sqlalchemy import select
        from velvetecho.database import paginate, PaginationParams

        stmt = select(Workspace).where(Workspace.name.like("%test%"))
        params = PaginationParams(page=1, limit=10)
        result = await paginate(session, stmt, params)

        for workspace in result.items:
            print(workspace.name)

        print(f"Page {result.page} of {result.total // result.limit + 1}")
    """
    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    # Get paginated items
    paginated_stmt = stmt.limit(params.limit).offset(params.offset)
    items_result = await session.execute(paginated_stmt)
    items = list(items_result.scalars().all())

    # Calculate pagination metadata
    has_next = (params.page * params.limit) < total
    has_prev = params.page > 1

    return PaginatedResult(
        items=items,
        total=total,
        page=params.page,
        limit=params.limit,
        has_next=has_next,
        has_prev=has_prev,
    )
