"""
Complete example showing Database + CQRS + API patterns.

This example demonstrates a full backend with:
1. Database models with mixins
2. Repository pattern
3. CQRS (Command/Query separation)
4. Auto-generated CRUD API
"""

from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional
from fastapi import FastAPI, Depends
from pydantic import BaseModel as PydanticModel
from sqlalchemy import Column, String, Text
from sqlalchemy.ext.asyncio import AsyncSession

# VelvetEcho imports
from velvetecho.database import (
    BaseModel,
    TimestampMixin,
    SoftDeleteMixin,
    Repository,
    init_database,
    get_session,
)
from velvetecho.cqrs import Command, Query, CommandHandler, QueryHandler, CommandBus, QueryBus
from velvetecho.api import StandardResponse, setup_middleware
from velvetecho.api.crud_router import CRUDRouter

# ============================================================================
# 1. Database Models
# ============================================================================


class Workspace(BaseModel, TimestampMixin, SoftDeleteMixin):
    """Workspace model with timestamps and soft delete"""

    __tablename__ = "workspaces"

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(String, nullable=False)


# ============================================================================
# 2. Pydantic Schemas
# ============================================================================


class WorkspaceCreate(PydanticModel):
    """Schema for creating workspace"""

    name: str
    description: Optional[str] = None
    created_by: str


class WorkspaceUpdate(PydanticModel):
    """Schema for updating workspace"""

    name: Optional[str] = None
    description: Optional[str] = None


class WorkspaceResponse(PydanticModel):
    """Schema for workspace response"""

    id: UUID
    name: str
    description: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============================================================================
# 3. Repository
# ============================================================================


class WorkspaceRepository(Repository[Workspace]):
    """Custom repository with additional methods"""

    async def get_by_name(self, name: str) -> Optional[Workspace]:
        """Get workspace by name"""
        from sqlalchemy import select

        stmt = select(Workspace).where(Workspace.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: str) -> list[Workspace]:
        """List workspaces created by user"""
        from sqlalchemy import select

        stmt = select(Workspace).where(Workspace.created_by == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


# ============================================================================
# 4. CQRS Commands
# ============================================================================


class CreateWorkspaceCommand(Command):
    """Command to create workspace"""

    name: str
    description: Optional[str]
    created_by: str


class UpdateWorkspaceCommand(Command):
    """Command to update workspace"""

    workspace_id: UUID
    name: Optional[str] = None
    description: Optional[str] = None


class DeleteWorkspaceCommand(Command):
    """Command to delete workspace"""

    workspace_id: UUID


# ============================================================================
# 5. CQRS Queries
# ============================================================================


class GetWorkspaceQuery(Query):
    """Query to get workspace by ID"""

    workspace_id: UUID


class ListWorkspacesQuery(Query):
    """Query to list workspaces"""

    user_id: Optional[str] = None
    limit: int = 10
    offset: int = 0


# ============================================================================
# 6. Command Handlers
# ============================================================================


class CreateWorkspaceHandler(CommandHandler[CreateWorkspaceCommand, Workspace]):
    """Handler for creating workspace"""

    def __init__(self, repository: WorkspaceRepository):
        self.repository = repository

    async def handle(self, command: CreateWorkspaceCommand) -> Workspace:
        """Create workspace"""
        workspace = Workspace(
            name=command.name,
            description=command.description,
            created_by=command.created_by,
        )
        return await self.repository.create(workspace)


class UpdateWorkspaceHandler(CommandHandler[UpdateWorkspaceCommand, Workspace]):
    """Handler for updating workspace"""

    def __init__(self, repository: WorkspaceRepository):
        self.repository = repository

    async def handle(self, command: UpdateWorkspaceCommand) -> Workspace:
        """Update workspace"""
        update_data = {}
        if command.name:
            update_data["name"] = command.name
        if command.description:
            update_data["description"] = command.description

        updated = await self.repository.update(command.workspace_id, update_data)

        if not updated:
            raise ValueError(f"Workspace not found: {command.workspace_id}")

        return updated


# ============================================================================
# 7. Query Handlers
# ============================================================================


class GetWorkspaceHandler(QueryHandler[GetWorkspaceQuery, Optional[Workspace]]):
    """Handler for getting workspace"""

    def __init__(self, repository: WorkspaceRepository):
        self.repository = repository

    async def handle(self, query: GetWorkspaceQuery) -> Optional[Workspace]:
        """Get workspace by ID"""
        return await self.repository.get_by_id(query.workspace_id)


class ListWorkspacesHandler(QueryHandler[ListWorkspacesQuery, list[Workspace]]):
    """Handler for listing workspaces"""

    def __init__(self, repository: WorkspaceRepository):
        self.repository = repository

    async def handle(self, query: ListWorkspacesQuery) -> list[Workspace]:
        """List workspaces"""
        if query.user_id:
            return await self.repository.list_by_user(query.user_id)
        return await self.repository.list(limit=query.limit, offset=query.offset)


# ============================================================================
# 8. FastAPI Application
# ============================================================================


def create_app() -> FastAPI:
    """Create FastAPI application"""
    app = FastAPI(title="VelvetEcho Complete Example")

    # Setup middleware
    setup_middleware(app)

    # Initialize database
    db = init_database("postgresql+asyncpg://user:pass@localhost/velvetecho_example")

    # Initialize CQRS buses
    command_bus = CommandBus()
    query_bus = QueryBus()

    # Dependency: Get repository
    def get_workspace_repository(session: AsyncSession = Depends(get_session)):
        return WorkspaceRepository(session, Workspace)

    # Register handlers
    def get_command_bus():
        return command_bus

    def get_query_bus():
        return query_bus

    # Register command handlers
    @app.on_event("startup")
    async def register_handlers():
        await db.connect()

        # Get a session to create handlers
        async with db.session() as session:
            repo = WorkspaceRepository(session, Workspace)

            # Register handlers
            command_bus.register(CreateWorkspaceCommand, CreateWorkspaceHandler(repo))
            command_bus.register(UpdateWorkspaceCommand, UpdateWorkspaceHandler(repo))

            query_bus.register(GetWorkspaceQuery, GetWorkspaceHandler(repo))
            query_bus.register(ListWorkspacesQuery, ListWorkspacesHandler(repo))

    @app.on_event("shutdown")
    async def shutdown():
        await db.disconnect()

    # ========================================================================
    # Option 1: Manual CQRS routes
    # ========================================================================

    @app.post("/api/workspaces/create", response_model=StandardResponse[WorkspaceResponse])
    async def create_workspace_via_cqrs(
        data: WorkspaceCreate,
        bus: CommandBus = Depends(get_command_bus),
    ):
        """Create workspace via CQRS"""
        command = CreateWorkspaceCommand(**data.model_dump())
        workspace = await bus.dispatch(command)

        return StandardResponse(
            data=WorkspaceResponse.model_validate(workspace),
            message="Workspace created via CQRS",
        )

    @app.get("/api/workspaces/{id}/cqrs", response_model=StandardResponse[WorkspaceResponse])
    async def get_workspace_via_cqrs(
        id: UUID,
        bus: QueryBus = Depends(get_query_bus),
    ):
        """Get workspace via CQRS"""
        query = GetWorkspaceQuery(workspace_id=id)
        workspace = await bus.dispatch(query)

        if not workspace:
            raise ValueError("Workspace not found")

        return StandardResponse(
            data=WorkspaceResponse.model_validate(workspace),
            message="Workspace retrieved via CQRS",
        )

    # ========================================================================
    # Option 2: Auto-generated CRUD routes
    # ========================================================================

    crud_router = CRUDRouter(
        model=Workspace,
        create_schema=WorkspaceCreate,
        update_schema=WorkspaceUpdate,
        response_schema=WorkspaceResponse,
        prefix="/api/workspaces",
        tags=["Workspaces"],
        get_repository=get_workspace_repository,
    )

    app.include_router(crud_router.router)

    return app


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    app = create_app()

    print("=" * 60)
    print("VelvetEcho Complete API Example")
    print("=" * 60)
    print()
    print("Features demonstrated:")
    print("✅ Database models (BaseModel + Mixins)")
    print("✅ Repository pattern")
    print("✅ CQRS (Commands + Queries)")
    print("✅ Auto-generated CRUD API")
    print()
    print("Endpoints:")
    print("  CRUD:")
    print("    GET    /api/workspaces (list)")
    print("    GET    /api/workspaces/{id}")
    print("    POST   /api/workspaces")
    print("    PUT    /api/workspaces/{id}")
    print("    DELETE /api/workspaces/{id}")
    print()
    print("  CQRS:")
    print("    POST /api/workspaces/create")
    print("    GET  /api/workspaces/{id}/cqrs")
    print()
    print("Starting server at http://localhost:8000")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8000)
