"""CRUD router generator for rapid API development"""

from typing import Type, Optional, Callable, List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from velvetecho.database.base import BaseModel as DBModel
from velvetecho.database.repository import Repository
from velvetecho.database.connection import get_session
from velvetecho.database.pagination import PaginationParams, paginate
from velvetecho.api.responses import StandardResponse, PaginatedResponse
from velvetecho.api.exceptions import NotFoundException


class CRUDRouter:
    """
    Auto-generate CRUD routes for a model.

    Generates:
    - GET /resources (list with pagination)
    - GET /resources/{id} (get by ID)
    - POST /resources (create)
    - PUT /resources/{id} (update)
    - DELETE /resources/{id} (delete)

    Example:
        from velvetecho.api import CRUDRouter
        from velvetecho.database import BaseModel, TimestampMixin

        # Define model
        class Workspace(BaseModel, TimestampMixin):
            __tablename__ = "workspaces"
            name = Column(String)

        # Define schemas
        class WorkspaceCreate(BaseModel):
            name: str

        class WorkspaceUpdate(BaseModel):
            name: Optional[str]

        class WorkspaceResponse(BaseModel):
            id: UUID
            name: str
            created_at: datetime

        # Generate router
        router = CRUDRouter(
            model=Workspace,
            create_schema=WorkspaceCreate,
            update_schema=WorkspaceUpdate,
            response_schema=WorkspaceResponse,
            prefix="/workspaces",
            tags=["Workspaces"],
        ).router

        # Mount in app
        app.include_router(router)
    """

    def __init__(
        self,
        model: Type[DBModel],
        create_schema: Type[BaseModel],
        update_schema: Type[BaseModel],
        response_schema: Type[BaseModel],
        prefix: str = "",
        tags: Optional[List[str]] = None,
        get_repository: Optional[Callable] = None,
    ):
        self.model = model
        self.create_schema = create_schema
        self.update_schema = update_schema
        self.response_schema = response_schema
        self.prefix = prefix
        self.tags = tags or []

        # Default repository getter
        if get_repository is None:

            def default_get_repository(session: AsyncSession = Depends(get_session)):
                return Repository(session, model)

            self.get_repository = default_get_repository
        else:
            self.get_repository = get_repository

        # Build router
        self.router = self._build_router()

    def _build_router(self) -> APIRouter:
        """Build FastAPI router with CRUD routes"""
        router = APIRouter(prefix=self.prefix, tags=self.tags)

        # List (with pagination)
        @router.get("/", response_model=PaginatedResponse[self.response_schema])
        async def list_items(
            page: int = Query(1, ge=1),
            limit: int = Query(10, ge=1, le=100),
            repo: Repository = Depends(self.get_repository),
        ):
            """List all items with pagination"""
            params = PaginationParams(page=page, limit=limit)

            # Import here to avoid circular import
            from sqlalchemy import select

            stmt = select(self.model)
            result = await paginate(repo.session, stmt, params)

            return PaginatedResponse.create(
                items=[self.response_schema.model_validate(item) for item in result.items],
                total=result.total,
                page=result.page,
                limit=result.limit,
            )

        # Get by ID
        @router.get("/{id}", response_model=StandardResponse[self.response_schema])
        async def get_item(
            id: UUID,
            repo: Repository = Depends(self.get_repository),
        ):
            """Get item by ID"""
            item = await repo.get_by_id(id)

            if not item:
                raise NotFoundException(self.model.__name__, id)

            return StandardResponse(
                data=self.response_schema.model_validate(item),
                message=f"{self.model.__name__} retrieved successfully",
            )

        # Create
        @router.post("/", response_model=StandardResponse[self.response_schema], status_code=201)
        async def create_item(
            data: self.create_schema,
            repo: Repository = Depends(self.get_repository),
        ):
            """Create new item"""
            item = self.model(**data.model_dump())
            created = await repo.create(item)

            return StandardResponse(
                data=self.response_schema.model_validate(created),
                message=f"{self.model.__name__} created successfully",
            )

        # Update
        @router.put("/{id}", response_model=StandardResponse[self.response_schema])
        async def update_item(
            id: UUID,
            data: self.update_schema,
            repo: Repository = Depends(self.get_repository),
        ):
            """Update item by ID"""
            # Only update fields that are set
            update_data = data.model_dump(exclude_unset=True)

            updated = await repo.update(id, update_data)

            if not updated:
                raise NotFoundException(self.model.__name__, id)

            return StandardResponse(
                data=self.response_schema.model_validate(updated),
                message=f"{self.model.__name__} updated successfully",
            )

        # Delete
        @router.delete("/{id}", status_code=204)
        async def delete_item(
            id: UUID,
            repo: Repository = Depends(self.get_repository),
        ):
            """Delete item by ID"""
            deleted = await repo.delete(id)

            if not deleted:
                raise NotFoundException(self.model.__name__, id)

        return router
