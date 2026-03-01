"""
Workspace API Router

Auto-generated CRUD + custom business logic routes for Workspaces.
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel as PydanticModel
from sqlalchemy import Column, String, Text
from datetime import datetime

from velvetecho.database import BaseModel, TimestampMixin, SoftDeleteMixin, Repository, get_session
from velvetecho.api import StandardResponse, PaginatedResponse
from velvetecho.api.crud_router import CRUDRouter
from velvetecho.api.exceptions import NotFoundException

# Router configuration (used by auto-discovery)
PREFIX = "/api/workspaces"
TAGS = ["Workspaces"]

# ============================================================================
# Database Model
# ============================================================================


class Workspace(BaseModel, TimestampMixin, SoftDeleteMixin):
    """Workspace database model"""

    __tablename__ = "workspaces"

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(String, nullable=False)


# ============================================================================
# Pydantic Schemas
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
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================================
# Custom Repository
# ============================================================================


class WorkspaceRepository(Repository[Workspace]):
    """Custom repository with domain-specific methods"""

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
# Router Setup
# ============================================================================

router = APIRouter()


# Dependency: Get repository
def get_workspace_repository(session: AsyncSession = Depends(get_session)):
    return WorkspaceRepository(session, Workspace)


# ============================================================================
# Auto-Generated CRUD Routes (5 endpoints)
# ============================================================================

crud_router = CRUDRouter(
    model=Workspace,
    create_schema=WorkspaceCreate,
    update_schema=WorkspaceUpdate,
    response_schema=WorkspaceResponse,
    prefix="",  # Already has /api/workspaces from auto-discovery
    get_repository=get_workspace_repository,
)

router.include_router(crud_router.router)

# ============================================================================
# Custom Business Logic Routes
# ============================================================================


@router.post("/{id}/archive", response_model=StandardResponse[WorkspaceResponse])
async def archive_workspace(
    id: UUID,
    repo: WorkspaceRepository = Depends(get_workspace_repository),
):
    """
    Archive workspace (soft delete)

    Custom business logic route demonstrating how to add
    domain-specific operations beyond CRUD.
    """
    workspace = await repo.get_by_id(id)

    if not workspace:
        raise NotFoundException("Workspace", id)

    # Soft delete
    await repo.delete(id)

    return StandardResponse(
        data=WorkspaceResponse.model_validate(workspace),
        message="Workspace archived successfully",
    )


@router.get("/{id}/statistics", response_model=StandardResponse[dict])
async def get_workspace_statistics(
    id: UUID,
    repo: WorkspaceRepository = Depends(get_workspace_repository),
):
    """
    Get workspace analytics and statistics

    Example of a custom query endpoint that returns
    computed data rather than direct model access.
    """
    workspace = await repo.get_by_id(id)

    if not workspace:
        raise NotFoundException("Workspace", id)

    # Compute statistics (example)
    stats = {
        "workspace_id": str(id),
        "name": workspace.name,
        "created_at": workspace.created_at.isoformat(),
        "days_active": (datetime.utcnow() - workspace.created_at).days,
        "is_archived": workspace.deleted_at is not None,
    }

    return StandardResponse(
        data=stats,
        message="Statistics retrieved successfully",
    )


@router.get("/user/{user_id}", response_model=StandardResponse[list[WorkspaceResponse]])
async def get_user_workspaces(
    user_id: str,
    repo: WorkspaceRepository = Depends(get_workspace_repository),
):
    """
    Get all workspaces for a specific user

    Example of using custom repository methods
    for domain-specific queries.
    """
    workspaces = await repo.list_by_user(user_id)

    return StandardResponse(
        data=[WorkspaceResponse.model_validate(w) for w in workspaces],
        message=f"Found {len(workspaces)} workspaces for user",
    )
